"""
Data loading utilities for the WC2026 quarterfinals dashboard.
Reads the 21 CSV tables per match (M97/M98/M99/M100) and unions them into
single dataframes per table, keyed on match_id, exactly as designed in the
Power BI build guide (star schema, same columns across all 4 matches).
"""
import glob
import os
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

TEAM_NAMES_PL = {
    "FRA": "Francja", "MAR": "Maroko", "ESP": "Hiszpania", "BEL": "Belgia",
    "NOR": "Norwegia", "ENG": "Anglia", "ARG": "Argentyna", "SUI": "Szwajcaria",
}
TEAM_FLAGS = {
    "FRA": "🇫🇷", "MAR": "🇲🇦", "ESP": "🇪🇸", "BEL": "🇧🇪",
    "NOR": "🇳🇴", "ENG": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ARG": "🇦🇷", "SUI": "🇨🇭",
}
MONTHS_PL = {
    1: "stycznia", 2: "lutego", 3: "marca", 4: "kwietnia", 5: "maja", 6: "czerwca",
    7: "lipca", 8: "sierpnia", 9: "września", 10: "października", 11: "listopada", 12: "grudnia",
}
CONFEDERATION_PL = {
    "UEFA": "Europa (UEFA)", "CAF": "Afryka (CAF)", "CONMEBOL": "Ameryka Południowa (CONMEBOL)",
    "CONCACAF": "Ameryka Płn./Środk. (CONCACAF)", "AFC": "Azja (AFC)", "OFC": "Oceania (OFC)",
}
SITUATION_PL = {
    "Regular Play": "Gra otwarta", "From Corner": "Z rzutu rożnego", "Penalty": "Rzut karny",
    "Cross": "Dośrodkowanie", "Counter Attack": "Kontratak", "Set Piece": "Stały fragment gry",
    "Free Kick": "Rzut wolny", "Fast Break": "Szybki atak", "Rebound": "Dobitka",
}
OUTCOME_PL = {
    "Saved": "Obroniony", "Blocked": "Zablokowany", "Off Target": "Niecelny",
    "Hit Woodwork": "Trafienie w słupek", "Goal": "Gol",
}


def build_match_labels(dim_match: pd.DataFrame) -> dict:
    """kto gra z kim, kiedy, gdzie i o której godzinie — no internal match numbers."""
    labels = {}
    for _, row in dim_match.iterrows():
        home = TEAM_NAMES_PL.get(row["home_team_id"], row["home_team_id"])
        away = TEAM_NAMES_PL.get(row["away_team_id"], row["away_team_id"])
        flag_h = TEAM_FLAGS.get(row["home_team_id"], "")
        flag_a = TEAM_FLAGS.get(row["away_team_id"], "")
        try:
            d = pd.to_datetime(row["match_date"])
            date_str = f"{d.day} {MONTHS_PL[d.month]}"
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


def team_label(team_id: str) -> str:
    return f"{TEAM_FLAGS.get(team_id, '')} {TEAM_NAMES_PL.get(team_id, team_id)}"
