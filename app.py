"""
FIFA World Cup 2026 — Quarterfinals tactical & statistical dashboard.
Built on the WC2026_M97/M98/M99/M100 star-schema dataset (21 CSV tables per match,
real-vs-modeled data flagged on every row via `data_source`).

Run locally:   streamlit run app.py
Deploy:        push this folder to a GitHub repo and deploy on
               Streamlit Community Cloud (share.streamlit.io) or Hugging Face Spaces.
"""
import base64
import io
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from data_loader import (load_all, MATCH_IDS, build_match_labels, team_label, TEAM_NAMES_PL, TEAM_FLAGS,
                          CONFEDERATION_PL, SITUATION_PL, OUTCOME_PL, POSITION_PL,
                          translate_substitution, translate_card)
from pitch_charts import shot_map, heatmap, pass_map

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

st.set_page_config(page_title="WC 2026 QF Dashboard", layout="wide")
st.logo(os.path.join(ASSETS_DIR, "kajodata_logo.png"))


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


WATERMARK_B64 = _b64(os.path.join(ASSETS_DIR, "kajodata_mark.png"))

st.markdown(f"""
<style>
.stTabs [data-baseweb="tab-list"] {{gap: 4px;}}
div[data-testid="stMetricValue"] {{font-size: 22px;}}

/* Lock the sidebar width — hide the drag handle so it can't be resized.
   Scoped to aria-expanded="true" so collapsing it still lets the main content
   area reclaim the freed space instead of leaving a blank gap. */
section[data-testid="stSidebar"][aria-expanded="true"] {{
    width: 320px !important;
    min-width: 320px !important;
    max-width: 320px !important;
}}
section[data-testid="stSidebar"] > div:not([data-testid="stSidebarContent"]) {{
    display: none !important;
    pointer-events: none !important;
}}

/* Logo ~200% bigger than Streamlit's default 24px — give the header room to grow. */
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
    height: auto;
    padding: 14px 0 6px 0;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarLogo"] {{
    width: 72px !important;
    height: 72px !important;
}}

/* Streamlit sizes this widget's container to its measured content width
   (narrower than the sidebar) — force it back to the full column width. */
section[data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(div[role="radiogroup"]),
section[data-testid="stSidebar"] div[data-testid="stRadio"],
section[data-testid="stSidebar"] div[role="radiogroup"] {{
    width: 100% !important;
}}

/* Nav "buttons": hide the radio dot, highlight the whole tile when selected,
   center the text, force equal height for every option regardless of content. */
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] {{
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
    min-height: 78px;
    padding: 10px 14px;
    margin-bottom: 6px;
    border-radius: 10px;
    border: 1px solid rgba(250,250,250,0.08);
    background: rgba(250,250,250,0.02);
    transition: background 0.15s ease;
}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover {{
    background: rgba(250,250,250,0.07);
}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) {{
    background: rgba(224,82,75,0.22);
    border-color: #e0524b;
}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div,
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div {{
    width: 100%;
    justify-content: center;
}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div > div:not([data-testid="stMarkdownContainer"]) {{
    display: none !important;
}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] {{
    width: 100%;
}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {{
    white-space: pre-line;
    text-align: center;
    line-height: 1.4;
    font-size: 13px;
    margin: 0;
}}
</style>
<img src="data:image/png;base64,{WATERMARK_B64}" style="
    position: fixed; bottom: 22px; right: 26px; width: 140px;
    opacity: 0.10; pointer-events: none; z-index: 5;">
""", unsafe_allow_html=True)

DATA = load_all()
MATCH_LABELS = build_match_labels(DATA["dim_match"])

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("⚽ WC 2026 QF Dashboard")
nav_options = ["Podsumowanie ćwierćfinałów"] + [MATCH_LABELS[m] for m in MATCH_IDS]
choice = st.sidebar.radio("Widok", nav_options, label_visibility="collapsed")

def match_id_from_choice(c):
    for m in MATCH_IDS:
        if MATCH_LABELS[m] == c:
            return m
    return None

MID = match_id_from_choice(choice)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def get_teams(mid):
    row = DATA["dim_match"].query("match_id == @mid").iloc[0]
    return row["home_team_id"], row["away_team_id"], row

def stat_comparison(stats_df, home_id, away_id):
    """Each row shows real values (as labels); bar length is scaled to that
    row's own max, not one shared axis — so a 3-shot gap isn't invisible next
    to an 80-point possession gap. Possession is the one row kept as a literal
    share of 100 (home% + away% == 100), since that's genuinely a percentage
    of a whole rather than an independent count. Home team's bar always runs
    left, away always right — matching the "Informacje i składy" tab layout."""
    s = stats_df.set_index("team_id")

    def val(team, col):
        return float(s.loc[team, col]) if team in s.index and col in s.columns else 0.0

    rows = []
    hp = val(home_id, "possession_pct")
    ap = 100 - hp
    rows.append(("Posiadanie piłki", -hp, ap, f"{hp:.0f}%", f"{ap:.0f}%"))

    count_metrics = [
        ("Strzały", "shots_total", "{:.0f}"),
        ("Strzały celne", "shots_on_target", "{:.0f}"),
        ("xG", "xg", "{:.2f}"),
        ("Podania", "passes_attempted", "{:.0f}"),
        ("Celność podań", "pass_accuracy_pct", "{:.0f}%"),
        ("Rzuty rożne", "corners", "{:.0f}"),
        ("Faule", "fouls_committed", "{:.0f}"),
    ]
    for label, col, fmt in count_metrics:
        hv, av = val(home_id, col), val(away_id, col)
        m = max(hv, av, 1e-9)
        rows.append((label, -(hv / m * 100), av / m * 100, fmt.format(hv), fmt.format(av)))

    fig = go.Figure()
    fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[r[1] for r in rows], orientation="h",
                          name=team_label(home_id), marker_color="#6cace4",
                          text=[r[3] for r in rows], textposition="outside"))
    fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[r[2] for r in rows], orientation="h",
                          name=team_label(away_id), marker_color="#e0524b",
                          text=[r[4] for r in rows], textposition="outside"))
    fig.update_layout(barmode="relative", height=44 * len(rows) + 60, template="plotly_dark",
                       margin=dict(l=10, r=10, t=10, b=10), bargap=0.45,
                       xaxis=dict(title="", range=[-135, 135], visible=False, zeroline=True, zerolinecolor="#3a4552"),
                       yaxis=dict(autorange="reversed"))
    return fig

def cumulative_xg(shots_df, home_id, away_id):
    """Cumulative xG derived live from the shot log, so it always matches the
    shot count / xG total shown elsewhere instead of drifting from a separately
    modeled time series."""
    s = shots_df.sort_values("minute")[["minute", "team_id", "xg"]].copy()
    s["home_cum"] = np.where(s["team_id"] == home_id, s["xg"], 0.0).cumsum()
    s["away_cum"] = np.where(s["team_id"] == away_id, s["xg"], 0.0).cumsum()
    origin = pd.DataFrame({"minute": [0], "home_cum": [0.0], "away_cum": [0.0]})
    return pd.concat([origin, s[["minute", "home_cum", "away_cum"]]], ignore_index=True)

def pyplot_html(fig, height=420):
    """Render a matplotlib figure as a fixed-height <img>, so it lines up with
    a Plotly chart of the same height sitting next to it in another column —
    st.pyplot alone scales only to the column's width, not a shared height."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=140, transparent=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f'<div style="height:{height}px; display:flex; align-items:center; justify-content:center;">'
            f'<img src="data:image/png;base64,{b64}" style="max-height:{height}px; max-width:100%; object-fit:contain;"></div>')

def add_end_label(fig, x_end, y_end, color, fmt="{:.2f}"):
    """Stamp the final value at the end of a cumulative line so the total is
    readable at a glance without hovering."""
    fig.add_annotation(x=x_end, y=y_end, text=fmt.format(y_end), showarrow=False,
                        xanchor="left", yanchor="middle", xshift=8,
                        font=dict(size=11, color=color, family="Arial Black"))
    return fig

def add_goal_markers(fig, goals_df):
    """A bare dashed line at the goal minute isn't self-explanatory — label
    each one with a ball icon, the minute and the scoring team's flag."""
    for _, g in goals_df.iterrows():
        flag = TEAM_FLAGS.get(g["team_id"], "")
        fig.add_vline(x=g["minute"], line_dash="dot", line_color="#f2c14e", opacity=0.55)
        fig.add_annotation(x=g["minute"], y=1.05, yref="paper", yanchor="bottom", xanchor="center",
                            text=f"⚽ {g['minute']}' {flag}", showarrow=False,
                            font=dict(size=10, color="#f2c14e"))
    return fig

# ---------------------------------------------------------------------------
# MATCH VIEW
# ---------------------------------------------------------------------------
if MID:
    home, away, mrow = get_teams(MID)
    shots = DATA["fact_shots"].query("match_id == @MID")
    # dim_player has no match_id column, but each team only appears in one quarterfinal,
    # so filtering by the two teams in this match scopes it correctly.
    players = DATA["dim_player"][DATA["dim_player"]["team_id"].isin([home, away])]
    team_stats = DATA["fact_team_match_stats"].query("match_id == @MID")
    timeline = DATA["fact_events_timeline"].query("match_id == @MID").sort_values("minute")
    momentum = DATA["fact_momentum"].query("match_id == @MID").sort_values("window_start")
    phases = DATA["fact_match_phases"].query("match_id == @MID")
    heat = DATA["fact_heatmap_zones"].query("match_id == @MID")
    zones = DATA["dim_pitch_zone"].drop_duplicates("zone_code")
    passes = DATA["fact_passes_into_box"].query("match_id == @MID")
    team_info = DATA["dim_team"].set_index("team_id")

    st.caption("⚽ ĆWIERĆFINAŁ · FIFA WORLD CUP 2026")
    c1, c2, c3 = st.columns([2, 3, 2])
    with c1:
        st.markdown(f"### {TEAM_FLAGS.get(home,'')} {mrow['home_score']} – {mrow['away_score']} {TEAM_FLAGS.get(away,'')}")
        st.caption(f"{TEAM_NAMES_PL.get(home)} vs {TEAM_NAMES_PL.get(away)}" + (" (dogrywka)" if mrow["extra_time"] == "Yes" else ""))
    with c2:
        st.markdown(f"**{mrow['venue']}** ({mrow['venue_broadcast_name']}) — {mrow['city']}")
        st.caption(f"{mrow['match_date']} · frekwencja {mrow['attendance']:,} · sędzia {mrow['referee']} ({mrow['referee_country']})")
    with c3:
        real_pct = (shots["data_source"].isin(["REAL", "REAL_EVENT_MODELED_XG", "REAL_OUTCOME_CORRECTED"]).mean() * 100)
        st.metric("Realne/zakotwiczone dane (strzały)", f"{real_pct:.0f}%")

    tabs = st.tabs(["Informacje i składy", "Statystyki ogólne", "Mapa strzałów i xG",
                    "Momenty meczu", "Fazy gry", "Heatmapy", "Wejścia w pole karne"])

    with tabs[0]:
        col1, col2 = st.columns(2)
        for col, team in [(col1, home), (col2, away)]:
            with col:
                st.subheader(team_label(team))
                if team in team_info.index:
                    trow = team_info.loc[team]
                    region = CONFEDERATION_PL.get(trow["confederation"], trow["confederation"])
                    st.caption(f"Trener: {trow['head_coach']} · Region: {region} · Ustawienie: {trow['formation']}")
                starters = players[(players["team_id"] == team) & (players["match_role"].str.contains("Starter"))].copy()
                starters["position"] = starters["position"].map(POSITION_PL).fillna(starters["position"])
                st.dataframe(starters[["position", "player_name"]].rename(
                    columns={"position": "Poz.", "player_name": "Zawodnik"}),
                    hide_index=True, use_container_width=True)
                subs = timeline[(timeline["team_id"] == team) & (timeline["event_name"] == "Substitution")]
                if len(subs):
                    st.markdown("**Zmiany**")
                    for _, r in subs.iterrows():
                        st.caption(f"{r['minute']}' — {translate_substitution(r['description'])}")
        st.markdown("---")
        goals = shots[shots["outcome"] == "Goal"].sort_values("minute")
        st.markdown("**Gole**")
        for _, g in goals.iterrows():
            pname = players.loc[players["player_id"] == g["player_id"], "player_name"]
            pname = pname.iloc[0] if len(pname) else g["player_id"]
            assist = ""
            if pd.notna(g.get("assist_player_id")) and g.get("assist_player_id"):
                aname = players.loc[players["player_id"] == g["assist_player_id"], "player_name"]
                assist = f" (asysta: {aname.iloc[0] if len(aname) else g['assist_player_id']})"
            st.caption(f"{g['minute']}' — {team_label(g['team_id'])} — {pname}{assist}")
        cards = timeline[timeline["event_name"].isin(["Yellow Card", "Red Card"])]
        if len(cards):
            st.markdown("**Kartki / zdarzenia dyscyplinarne**")
            for _, r in cards.iterrows():
                st.caption(f"{r['minute']}' — {translate_card(r['description'])}")

    with tabs[1]:
        st.caption("Zakładka dostępna wyłącznie na poziomie pojedynczego meczu — pełny box score. "
                   "Strzały/celne/xG liczone bezpośrednio z logu strzałów, więc pokrywają się z zakładką „Mapa strzałów i xG”.")
        shots_agg = shots.groupby("team_id").agg(
            shots_total=("shot_id", "count"),
            shots_on_target=("outcome", lambda s: s.isin(["Goal", "Saved"]).sum()),
            xg=("xg", "sum"),
        ).reset_index()
        display_stats = team_stats.drop(columns=["shots_total", "shots_on_target", "xg"]).merge(shots_agg, on="team_id")
        st.plotly_chart(stat_comparison(display_stats, home, away), use_container_width=True)

    with tabs[2]:
        show = (shots.merge(players[["player_id", "player_name"]], on="player_id", how="left")
                .sort_values("minute").reset_index(drop=True))
        show["celny"] = show["outcome"].isin(["Goal", "Saved"])

        table_key = f"shot_log_{MID}"
        sel = st.session_state.get(table_key, {})
        sel_rows = sel.get("selection", {}).get("rows", []) if sel else []
        highlight_id = show.iloc[sel_rows[0]]["shot_id"] if sel_rows else None

        CHART_H = 420
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(pyplot_html(shot_map(shots, home, away, highlight_shot_id=highlight_id), height=CHART_H),
                        unsafe_allow_html=True)
        with c2:
            xgc = cumulative_xg(shots, home, away)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xgc["minute"], y=xgc["home_cum"], name=team_label(home),
                                      line=dict(color="#6cace4", shape="hv"),
                                      hovertemplate="minuta %{x}<br>xG: %{y:.2f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=xgc["minute"], y=xgc["away_cum"], name=team_label(away),
                                      line=dict(color="#e0524b", shape="hv"),
                                      hovertemplate="minuta %{x}<br>xG: %{y:.2f}<extra></extra>"))
            add_goal_markers(fig, goals)
            last = xgc.iloc[-1]
            add_end_label(fig, last["minute"], last["home_cum"], "#6cace4")
            add_end_label(fig, last["minute"], last["away_cum"], "#e0524b")
            fig.update_layout(template="plotly_dark", height=CHART_H, xaxis_title="minuta", yaxis_title="skumulowane xG",
                               margin=dict(l=10, r=36, t=46, b=10),
                               xaxis=dict(range=[0, last["minute"] + 8]))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Lista strzałów** — kliknij wiersz, aby podświetlić ten strzał na mapie; kliknij nagłówek kolumny, aby posortować.")
        show_display = show[["minute", "team_id", "player_name", "situation", "outcome", "xg", "celny"]].copy()
        show_display["situation"] = show_display["situation"].map(SITUATION_PL).fillna(show_display["situation"])
        show_display["outcome"] = show_display["outcome"].map(OUTCOME_PL).fillna(show_display["outcome"])
        st.dataframe(
            show_display.rename(columns={"minute": "Min", "team_id": "Zespół", "player_name": "Zawodnik",
                                          "situation": "Sytuacja", "outcome": "Wynik", "xg": "xG",
                                          "celny": "Celny"}),
            hide_index=True, use_container_width=True, height=340,
            key=table_key, on_select="rerun", selection_mode="single-row")

    with tabs[3]:
        st.caption("Przewaga (momentum) w kolejnych oknach czasowych meczu — słupek w górę = przewaga "
                   f"gospodarza ({team_label(home)}), w dół = przewaga gościa ({team_label(away)}).")
        widths = (momentum["window_end"] - momentum["window_start"]) * 0.92
        centers = (momentum["window_start"] + momentum["window_end"]) / 2
        fig = go.Figure()
        fig.add_trace(go.Bar(x=centers, y=momentum["home_momentum_score"], width=widths,
                              name=team_label(home), marker_color="#6cace4", hoverinfo="skip",
                              text=[f"{v:.0f}%" for v in momentum["home_momentum_score"]],
                              textposition="inside", textfont=dict(size=9, color="#0e1117")))
        fig.add_trace(go.Bar(x=centers, y=-momentum["away_momentum_score"], width=widths,
                              name=team_label(away), marker_color="#e0524b", hoverinfo="skip",
                              text=[f"{v:.0f}%" for v in momentum["away_momentum_score"]],
                              textposition="inside", textfont=dict(size=9, color="#0e1117")))
        add_goal_markers(fig, goals)
        fig.update_layout(template="plotly_dark", height=320, barmode="relative", hovermode=False,
                           margin=dict(l=10, r=10, t=46, b=10), xaxis_title="minuta",
                           yaxis=dict(title="momentum", zeroline=True, zerolinecolor="#4a5568",
                                      zerolinewidth=1.4, showticklabels=False))
        st.plotly_chart(fig, use_container_width=True)

    with tabs[4]:
        phases_calc = phases.copy()
        phases_calc["transition_pct"] = phases_calc["transition_off_def_pct"] + phases_calc["transition_def_off_pct"]
        phase_types = [("Atak", "attack_pct"), ("Przejściowa", "transition_pct"), ("Obrona", "defense_pct")]
        PHASE_COLORS = {"Atak": "#3fbf7f", "Przejściowa": "#f2b134", "Obrona": "#e0524b"}
        # The bar chart below and the donut both derive from these same per-window
        # shares — the donut just expresses them as minutes (ilość) instead of %,
        # so the two views stay proportionally consistent with each other.
        avg = phases_calc.groupby("team_id")[["attack_pct", "transition_pct", "defense_pct"]].mean()
        phases_calc["window_len"] = phases_calc["window_end"] - phases_calc["window_start"]
        for _, col_name in phase_types:
            phases_calc[f"{col_name}_min"] = phases_calc[col_name] / 100 * phases_calc["window_len"]
        minutes_sum = phases_calc.groupby("team_id")[[f"{c}_min" for _, c in phase_types]].sum()

        st.markdown("**Ilość faz gry (w minutach)**")
        c1, c2 = st.columns(2)
        for col, team in [(c1, home), (c2, away)]:
            with col:
                st.caption(team_label(team))
                values = [minutes_sum.loc[team, f"{col_name}_min"] if team in minutes_sum.index else 0
                          for _, col_name in phase_types]
                labels = [label for label, _ in phase_types]
                fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55,
                                        marker=dict(colors=[PHASE_COLORS[l] for l in labels]),
                                        texttemplate="%{label}<br>%{value:.0f} min", sort=False,
                                        hovertemplate="%{label}: %{percent}<extra></extra>"))
                fig.update_layout(template="plotly_dark", height=260, showlegend=False,
                                   margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Średni udział faz w liczbach**")
        fig = go.Figure()
        for label, col_name in phase_types:
            minutes_col = f"{col_name}_min"
            fig.add_trace(go.Bar(
                y=[team_label(home), team_label(away)],
                x=[avg.loc[t, col_name] if t in avg.index else 0 for t in (home, away)],
                name=label, orientation="h", marker_color=PHASE_COLORS[label],
                text=[f"{avg.loc[t, col_name]:.0f}%" if t in avg.index else "" for t in (home, away)],
                textposition="inside", insidetextanchor="middle",
                customdata=[minutes_sum.loc[t, minutes_col] if t in minutes_sum.index else 0 for t in (home, away)],
                hovertemplate="%{customdata:.0f} min<extra></extra>"))
        fig.update_layout(barmode="stack", template="plotly_dark", height=220,
                           margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(title="%", range=[0, 100]),
                           yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with tabs[5]:
        st.caption("Wybierz zawodnika osobno dla każdej drużyny — lista zawiera tylko graczy z tego meczu. "
                   "Dla wybranego zawodnika mapa dotknięć w poszczególnych strefach jest dodatkowo naniesiona jako punkty "
                   "(surowych współrzędnych GPS nie mamy — tylko zagregowaną liczbę dotknięć w każdej z 30 stref).")
        c1, c2 = st.columns(2)
        for col, team in [(c1, home), (c2, away)]:
            with col:
                st.subheader(team_label(team))
                played = players[(players["team_id"] == team) & (~players["match_role"].str.contains("unused", case=False, na=False))]
                team_players = sorted(played["player_name"].dropna().unique().tolist())
                opt = st.selectbox("Zawodnik", ["Cały zespół"] + team_players, key=f"heat_sel_{team}")
                if opt == "Cały zespół":
                    st.pyplot(heatmap(heat, zones, team), use_container_width=True)
                else:
                    pid = players.loc[(players["player_name"] == opt) & (players["team_id"] == team), "player_id"].iloc[0]
                    st.pyplot(heatmap(heat[heat["player_id"] == pid], zones, team, show_points=True),
                               use_container_width=True)

    with tabs[6]:
        c1, c2 = st.columns(2)
        for col, team in [(c1, home), (c2, away)]:
            with col:
                st.subheader(team_label(team))
                st.pyplot(pass_map(passes, team), use_container_width=True)
                sub = passes[passes["team_id"] == team]
                succ = (sub["outcome"] == "Successful").mean() * 100 if len(sub) else 0
                led = (sub["led_to_shot_within_10s"] == "Yes").mean() * 100 if len(sub) else 0
                cA, cB, cC = st.columns(3)
                cA.metric("Wejścia", len(sub))
                cB.metric("Skuteczność", f"{succ:.0f}%")
                cC.metric("→ strzał", f"{led:.0f}%")

# ---------------------------------------------------------------------------
# TOURNAMENT AGGREGATE VIEW
# ---------------------------------------------------------------------------
else:
    st.markdown("## FIFA World Cup 2026 — Ćwierćfinały — panel zbiorczy")
    tabs = st.tabs(["Podsumowanie", "Mapa strzałów i xG", "Momenty meczu",
                    "Fazy gry", "Heatmapy", "Wejścia w pole karne"])

    dm = DATA["dim_match"]
    shots_all = DATA["fact_shots"]
    stats_all = DATA["fact_team_match_stats"]
    phases_all = DATA["fact_match_phases"]
    heat_all = DATA["fact_heatmap_zones"]
    zones_all = DATA["dim_pitch_zone"]
    passes_all = DATA["fact_passes_into_box"]

    with tabs[0]:
        cols = st.columns(4)
        total_goals = int((dm["home_score"] + dm["away_score"]).sum())
        cols[0].metric("Goli łącznie", total_goals)
        cols[1].metric("Śr. goli / mecz", round(total_goals / len(dm), 2))
        cols[2].metric("Mecze po dogrywce", f"{(dm['extra_time'] == 'Yes').sum()}/{len(dm)}")
        cols[3].metric("Czerwone kartki", int((DATA['fact_team_match_stats']['red_cards']).sum()))
        table = dm.merge(stats_all.groupby("match_id")["xg"].apply(list).reset_index(), on="match_id")
        display = dm[["match_id", "home_team_id", "away_team_id", "home_score", "away_score", "extra_time"]].copy()
        display["Mecz"] = display["home_team_id"].map(TEAM_NAMES_PL) + " – " + display["away_team_id"].map(TEAM_NAMES_PL)
        display["extra_time"] = display["extra_time"].map({"Yes": "Tak", "No": "Nie"})
        st.dataframe(display[["Mecz", "home_score", "away_score", "extra_time"]].rename(
            columns={"home_score": "Gospodarz", "away_score": "Gość", "extra_time": "Dogrywka"}),
            hide_index=True, use_container_width=True)
        st.caption("Strona zbiorcza pokazuje dane zsumowane ze wszystkich 4 ćwierćfinałów. Wybierz mecz w panelu bocznym, by zobaczyć pełne szczegóły (składy, zmiany, statystyki ogólne).")

    with tabs[1]:
        CHART_H = 380
        c1, c2 = st.columns(2)
        with c1:
            xg_by_team = shots_all.groupby("team_id")["xg"].sum().sort_values(ascending=False)
            fig = px.bar(x=xg_by_team.index.map(TEAM_NAMES_PL), y=xg_by_team.values, labels={"x": "", "y": "xG"})
            fig.update_traces(texttemplate="%{y:.2f}", textposition="outside",
                               hovertemplate="%{x}<br>xG: %{y:.2f}<extra></extra>")
            fig.update_layout(template="plotly_dark", height=CHART_H, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            PALETTE = ["#6cace4", "#e0524b", "#3fbf7f", "#f2b134"]
            fig = go.Figure()
            max_minute = 0
            for i, mid in enumerate(MATCH_IDS):
                mrow = dm.loc[dm["match_id"] == mid].iloc[0]
                xgc = cumulative_xg(shots_all.query("match_id == @mid"), mrow["home_team_id"], mrow["away_team_id"])
                pair = f"{TEAM_NAMES_PL.get(mrow['home_team_id'])} – {TEAM_NAMES_PL.get(mrow['away_team_id'])}"
                total = xgc["home_cum"] + xgc["away_cum"]
                color = PALETTE[i % len(PALETTE)]
                fig.add_trace(go.Scatter(x=xgc["minute"], y=total, name=pair, line=dict(shape="hv", color=color),
                                          hovertemplate="minuta %{x}<br>xG: %{y:.2f}<extra></extra>"))
                last_x, last_y = xgc["minute"].iloc[-1], total.iloc[-1]
                add_end_label(fig, last_x, last_y, color)
                max_minute = max(max_minute, last_x)
            fig.update_layout(template="plotly_dark", height=CHART_H, xaxis_title="minuta", yaxis_title="łączne xG",
                               margin=dict(l=10, r=36, t=10, b=10), xaxis=dict(range=[0, max_minute + 8]))
            st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        bins = [0, 15, 30, 45, 60, 75, 90, 130]
        labels = ["0-15'", "16-30'", "31-45'", "46-60'", "61-75'", "76-90'", "Dogrywka"]
        goals_all = shots_all[shots_all["outcome"] == "Goal"].copy()
        goals_all["bucket"] = pd.cut(goals_all["minute"], bins=bins, labels=labels, right=True)
        counts = goals_all["bucket"].value_counts().reindex(labels, fill_value=0)
        fig = px.bar(x=counts.index, y=counts.values, labels={"x": "", "y": "liczba goli"})
        fig.update_traces(hovertemplate="%{x}<br>Gole: %{y}<extra></extra>")
        fig.update_layout(template="plotly_dark", height=380, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Rozkład minut, w których padły gole — zsumowany z 4 meczów (12 goli łącznie).")

    with tabs[3]:
        phases_all_calc = phases_all.copy()
        phases_all_calc["transition_pct"] = (phases_all_calc["transition_off_def_pct"]
                                               + phases_all_calc["transition_def_off_pct"])
        avg_phase = phases_all_calc.groupby("team_id")[["attack_pct", "transition_pct", "defense_pct"]].mean()
        avg_phase = avg_phase.rename(columns={"attack_pct": "Atak", "transition_pct": "Przejściowa",
                                                "defense_pct": "Obrona"})
        fig = px.bar(avg_phase, orientation="h", labels={"value": "%", "team_id": ""},
                     color_discrete_map={"Atak": "#3fbf7f", "Przejściowa": "#f2b134", "Obrona": "#e0524b"})
        fig.update_traces(texttemplate="%{x:.0f}%", textposition="inside", insidetextanchor="middle",
                           hovertemplate="%{x:.0f}%<extra></extra>")
        fig.update_layout(template="plotly_dark", height=380, margin=dict(l=10, r=10, t=10, b=10),
                           xaxis=dict(range=[0, 100]),
                           yaxis=dict(ticktext=[TEAM_NAMES_PL.get(t, t) for t in avg_phase.index],
                                      tickvals=list(range(len(avg_phase)))))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Średni udział faz zsumowany po oknach czasowych każdego meczu.")

    with tabs[4]:
        thirds = zones_all.drop_duplicates("zone_code")[["zone_code"]].copy()
        thirds["third"] = thirds["zone_code"].apply(lambda z: "Obrona" if int(z[1]) <= 2 else ("Środek" if int(z[1]) <= 4 else "Atak"))
        heat_thirds = heat_all.merge(thirds, on="zone_code", how="left")
        agg = heat_thirds.groupby(["team_id", "third"])["touches"].sum().reset_index()
        totals = agg.groupby("team_id")["touches"].transform("sum")
        agg["pct"] = agg["touches"] / totals * 100
        fig = px.bar(agg, x="team_id", y="pct", color="third", barmode="stack",
                     color_discrete_map={"Obrona": "#e0524b", "Środek": "#f2b134", "Atak": "#3fbf7f"},
                     labels={"team_id": "", "pct": "% dotknięć"})
        fig.update_traces(texttemplate="%{y:.0f}%", textposition="inside", insidetextanchor="middle", hoverinfo="skip")
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), hovermode=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Pełna siatka 30 stref jest czytelna tylko dla jednego meczu/drużyny — tu uproszczone porównanie obrona/środek/atak dla wszystkich 8 zespołów.")

    with tabs[5]:
        succ = passes_all.groupby("team_id").apply(lambda d: (d["outcome"] == "Successful").mean() * 100).sort_values(ascending=False)
        fig = px.bar(x=succ.index.map(TEAM_NAMES_PL), y=succ.values, labels={"x": "", "y": "Skuteczność wejść w pole karne %"})
        fig.update_traces(texttemplate="%{y:.0f}%", textposition="inside", insidetextanchor="middle",
                           hovertemplate="%{x}<br>Skuteczność: %{y:.0f}%<extra></extra>")
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Mapa strzałek podań w pole karne jest czytelna tylko per mecz — dostępna na stronie każdego meczu.")
