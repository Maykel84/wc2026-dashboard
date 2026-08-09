"""
Data loading utilities for the WC2026 quarterfinals dashboard.
Reads the 21 CSV tables per match (M97/M98/M99/M100) and unions them into
single dataframes per table, keyed on match_id, exactly as designed in the
Power BI build guide (star schema, same columns across all 4 matches).

English is the site's default language; Polish is a fully supported second
language selectable from the sidebar. Every user-facing lookup below is
keyed by lang ("en" / "pl"); functions that don't take an explicit lang
argument fall back to st.session_state["lang"] (set by the language switcher
in app.py) so existing call sites don't all need to pass it explicitly.
"""
import os
import re
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

MATCH_IDS = ["WC2026_M97", "WC2026_M98", "WC2026_M99", "WC2026_M100"]

TABLES = [
    "dim_match", "dim_team", "dim_player", "dim_pitch_zone", "dim_event_type", "dim_phase",
    "fact_team_match_stats", "fact_player_match_stats", "fact_events_timeline", "fact_shots",
    "fact_xg_cumulative", "fact_momentum", "fact_match_phases", "fact_pressing",
    "fact_passes_into_box", "fact_heatmap_zones", "fact_tactical_comparison", "fact_team_form",
    "fact_betting_odds", "fact_set_pieces", "fact_possession_sequences",
]

DEFAULT_LANG = "en"

TEAM_NAMES = {
    "en": {"FRA": "France", "MAR": "Morocco", "ESP": "Spain", "BEL": "Belgium",
           "NOR": "Norway", "ENG": "England", "ARG": "Argentina", "SUI": "Switzerland"},
    "pl": {"FRA": "Francja", "MAR": "Maroko", "ESP": "Hiszpania", "BEL": "Belgia",
           "NOR": "Norwegia", "ENG": "Anglia", "ARG": "Argentyna", "SUI": "Szwajcaria"},
}
# Kept for any old call sites that still import the PL-only name directly.
TEAM_NAMES_PL = TEAM_NAMES["pl"]

TEAM_FLAGS = {
    "FRA": "🇫🇷", "MAR": "🇲🇦", "ESP": "🇪🇸", "BEL": "🇧🇪",
    "NOR": "🇳🇴", "ENG": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ARG": "🇦🇷", "SUI": "🇨🇭",
}

MONTHS = {
    "en": {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
           7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"},
    "pl": {1: "stycznia", 2: "lutego", 3: "marca", 4: "kwietnia", 5: "maja", 6: "czerwca",
           7: "lipca", 8: "sierpnia", 9: "września", 10: "października", 11: "listopada", 12: "grudnia"},
}

CONFEDERATION = {
    "en": {"UEFA": "Europe (UEFA)", "CAF": "Africa (CAF)", "CONMEBOL": "South America (CONMEBOL)",
           "CONCACAF": "North/Central America (CONCACAF)", "AFC": "Asia (AFC)", "OFC": "Oceania (OFC)"},
    "pl": {"UEFA": "Europa (UEFA)", "CAF": "Afryka (CAF)", "CONMEBOL": "Ameryka Południowa (CONMEBOL)",
           "CONCACAF": "Ameryka Płn./Środk. (CONCACAF)", "AFC": "Azja (AFC)", "OFC": "Oceania (OFC)"},
}

# The raw fact_shots.situation/outcome values are already the canonical English
# terms, so the "en" maps here are just identities — kept explicit (rather than
# omitted) so display code can always go through the same .map(...) call.
SITUATION = {
    "en": {"Regular Play": "Regular Play", "From Corner": "From Corner", "Penalty": "Penalty",
           "Cross": "Cross", "Counter Attack": "Counter Attack", "Set Piece": "Set Piece",
           "Free Kick": "Free Kick", "Fast Break": "Fast Break", "Rebound": "Rebound"},
    "pl": {"Regular Play": "Gra otwarta", "From Corner": "Z rzutu rożnego", "Penalty": "Rzut karny",
           "Cross": "Dośrodkowanie", "Counter Attack": "Kontratak", "Set Piece": "Stały fragment gry",
           "Free Kick": "Rzut wolny", "Fast Break": "Szybki atak", "Rebound": "Dobitka"},
}
OUTCOME = {
    "en": {"Saved": "Saved", "Blocked": "Blocked", "Off Target": "Off Target",
           "Hit Woodwork": "Hit Woodwork", "Goal": "Goal"},
    "pl": {"Saved": "Obroniony", "Blocked": "Zablokowany", "Off Target": "Niecelny",
           "Hit Woodwork": "Trafienie w słupek", "Goal": "Gol"},
}
POSITION = {
    "en": {"GK": "GK", "DEF": "DEF", "MID": "MID", "FWD": "FWD"},
    "pl": {"GK": "BR", "DEF": "OBR", "MID": "POM", "FWD": "NAP"},
}

# Back-compat aliases for the PL-only names used before the i18n pass.
CONFEDERATION_PL = CONFEDERATION["pl"]
SITUATION_PL = SITUATION["pl"]
OUTCOME_PL = OUTCOME["pl"]
POSITION_PL = POSITION["pl"]


def _lang(lang):
    return lang or st.session_state.get("lang", DEFAULT_LANG)


# The ~30 substitution descriptions in the raw (English) data follow a regular
# "X replaces Y[, note]." shape, so a single regex covers a Polish rewrite;
# card descriptions are far more varied in structure but there are only 7
# total across all 4 matches, so those are translated verbatim instead.
_SUB_NOTE_PL = {
    "Zaïre-Emery's World Cup debut": "debiut Zaïre-Emery'ego na Mistrzostwach Świata",
    "injury": "kontuzja",
}
_SUB_RE = re.compile(r"^(.+?) replaces (?:goalscorer )?(.+?)( late in extra time)?(?:\s*\((.+?)\))?\.$")


def translate_substitution(description: str, lang: str = None) -> str:
    if _lang(lang) != "pl":
        return description
    m = _SUB_RE.match(description.strip())
    if not m:
        return description
    player_in, player_out, extra_time, note = m.groups()
    text = f"{player_in} wchodzi za {player_out}"
    if extra_time:
        text += " (dogrywka)"
    if note and "readme" not in note.lower():
        text += f" ({_SUB_NOTE_PL.get(note.strip(), note)})"
    return text + "."


CARD_DESCRIPTIONS_PL = {
    "Issa Diop booked for serious foul play.":
        "Issa Diop ukarany żółtą kartką za poważny faul.",
    "Charles De Ketelaere booked shortly after his equalizer.":
        "Charles De Ketelaere ukarany żółtą kartką wkrótce po golu wyrównującym.",
    "Pau Cubarsí booked for a tactical foul.":
        "Pau Cubarsí ukarany żółtą kartką za faul taktyczny.",
    "Aymeric Laporte booked for time-wasting/tactical foul in stoppage time.":
        "Aymeric Laporte ukarany żółtą kartką za grę na czas / faul taktyczny w doliczonym czasie.",
    "Kristoffer Ajer booked for protesting the referee's decision.":
        "Kristoffer Ajer ukarany żółtą kartką za protestowanie przeciwko decyzji sędziego.",
    "Leandro Paredes initially shown a yellow card for a foul on Breel Embolo.":
        "Leandro Paredes początkowo ukarany żółtą kartką za faul na Breelu Embolo.",
    "Breel Embolo shown a second yellow (reassigned card) and sent off - the first application "
    "of IFAB's 'mistaken identity' VAR protocol at a men's World Cup. Switzerland reduced to 10 men.":
        "Breel Embolo otrzymał drugą żółtą kartkę (skorygowaną decyzją VAR) i został wyrzucony z boiska "
        "— pierwszy przypadek zastosowania protokołu VAR ds. „pomyłki tożsamości” IFAB na mistrzostwach "
        "świata mężczyzn. Szwajcaria w 10 osób.",
}


def translate_card(description: str, lang: str = None) -> str:
    if _lang(lang) != "pl":
        return description
    return CARD_DESCRIPTIONS_PL.get(description.strip(), description)


def build_match_labels(dim_match: pd.DataFrame, lang: str = None) -> dict:
    """who plays whom, when, where and at what time — no internal match numbers."""
    lang = _lang(lang)
    labels = {}
    for _, row in dim_match.iterrows():
        home = TEAM_NAMES[lang].get(row["home_team_id"], row["home_team_id"])
        away = TEAM_NAMES[lang].get(row["away_team_id"], row["away_team_id"])
        flag_h = TEAM_FLAGS.get(row["home_team_id"], "")
        flag_a = TEAM_FLAGS.get(row["away_team_id"], "")
        try:
            d = pd.to_datetime(row["match_date"])
            date_str = f"{MONTHS[lang][d.month]} {d.day}" if lang == "en" else f"{d.day} {MONTHS[lang][d.month]}"
        except Exception:
            date_str = str(row["match_date"])
        kickoff = str(row.get("kickoff_local", "")).split("/")[0].strip()
        city = row.get("city", "")
        # Hard line breaks (trailing double-space) so the sidebar button shows three
        # separate, non-wrapping lines instead of one long squeezed string.
        labels[row["match_id"]] = (f"{flag_h} {home} – {away} {flag_a}  \n"
                                    f"{date_str}, {kickoff}  \n"
                                    f"{city}")
    return labels


@st.cache_data
def load_table(table_name: str) -> pd.DataFrame:
    frames = []
    for mid in MATCH_IDS:
        path = os.path.join(DATA_DIR, f"{mid}_{table_name}.csv")
        if os.path.exists(path):
            frames.append(pd.read_csv(path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data
def load_all() -> dict:
    return {t: load_table(t) for t in TABLES}


def team_label(team_id: str, lang: str = None) -> str:
    lang = _lang(lang)
    return f"{TEAM_FLAGS.get(team_id, '')} {TEAM_NAMES[lang].get(team_id, team_id)}"
