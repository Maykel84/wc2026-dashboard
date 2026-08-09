"""
mplsoccer-based pitch visualizations: shot maps, heatmaps, pass-into-box maps.
Pitch is 105x68, both teams already normalized to attack right (toward x=105, y=34),
matching the coordinate convention used across all fact_shots / fact_passes_into_box
/ dim_pitch_zone tables in the WC2026 dataset.

These charts are rendered as static matplotlib images, so any on-image text
(titles, zone labels, colorbar) is baked in at render time — pass lang="pl" to
get the Polish labels; English ("en") is the default.
"""
import numpy as np
import matplotlib.pyplot as plt
from mplsoccer import Pitch

OUTCOME_COLORS = {
    "Goal": "#f2c14e", "Saved": "#3fbf7f", "Blocked": "#6cace4",
    "Off Target": "#8a8f98", "Hit Woodwork": "#e0524b",
}

HEATMAP_CMAP = "RdYlGn_r"  # green = few touches, red = many touches

LABELS = {
    "en": {
        "shot_map_title": "Size = xG · star = goal",
        "touches": "touches",
        "thirds": ("DEFENSE", "MIDFIELD", "ATTACK"),
        "pass_map_title": "Green = successful · dashed = unsuccessful · gold = led to a shot",
    },
    "pl": {
        "shot_map_title": "Rozmiar = xG · gwiazdka = gol",
        "touches": "dotknięcia",
        "thirds": ("OBRONA", "POMOC", "ATAK"),
        "pass_map_title": "Zielone = skuteczne · przerywane = nieskuteczne · złote = poprowadziło do strzału",
    },
}


def make_pitch(figsize=(8, 5.2), pitch_color="#0e1117", line_color="#4a5568", line_zorder=0.9):
    pitch = Pitch(pitch_type="custom", pitch_length=105, pitch_width=68,
                   pitch_color=pitch_color, line_color=line_color, linewidth=1,
                   line_zorder=line_zorder)
    fig, ax = pitch.draw(figsize=figsize)
    fig.patch.set_alpha(0)
    return pitch, fig, ax


def shot_map(shots_df, home_id, away_id, home_color="#6cace4", away_color="#e0524b",
             highlight_shot_id=None, lang="en"):
    L = LABELS.get(lang, LABELS["en"])
    pitch, fig, ax = make_pitch()
    for team, base_color in [(home_id, home_color), (away_id, away_color)]:
        sub = shots_df[shots_df["team_id"] == team]
        sizes = 80 + sub["xg"].clip(lower=0) * 900
        is_goal = sub["outcome"] == "Goal"
        pitch.scatter(sub.loc[~is_goal, "x_norm"], sub.loc[~is_goal, "y_norm"],
                      s=sizes[~is_goal], color=base_color, edgecolors="white",
                      linewidth=0.4, alpha=0.75, ax=ax, zorder=2)
        pitch.scatter(sub.loc[is_goal, "x_norm"], sub.loc[is_goal, "y_norm"],
                      s=sizes[is_goal], color="#f2c14e", edgecolors=base_color,
                      linewidth=2.2, alpha=0.95, ax=ax, zorder=3, marker="*")

    if highlight_shot_id is not None:
        hl = shots_df[shots_df["shot_id"] == highlight_shot_id]
        if len(hl):
            hx, hy = hl.iloc[0]["x_norm"], hl.iloc[0]["y_norm"]
            hsize = 80 + max(hl.iloc[0]["xg"], 0) * 900
            # Two concentric rings around the clicked scorer's shot — visible over
            # any marker color/size so it stands out regardless of team or xG.
            pitch.scatter([hx], [hy], s=hsize * 3.4, facecolors="none",
                          edgecolors="white", linewidth=2.6, ax=ax, zorder=5)
            pitch.scatter([hx], [hy], s=hsize * 6.0, facecolors="none",
                          edgecolors="#f2c14e", linewidth=1.8, linestyle=(0, (3, 2)), ax=ax, zorder=4)
            ax.annotate(f"{hl.iloc[0]['minute']:.0f}'", (hx, hy), xytext=(0, 15),
                        textcoords="offset points", color="#f2c14e", fontsize=9,
                        fontweight="bold", ha="center", zorder=6)

    ax.set_title(L["shot_map_title"], color="#9aa4b2", fontsize=9, loc="left")
    return fig


def heatmap(heat_df, zone_df, team_id, cmap=None, lang="en"):
    L = LABELS.get(lang, LABELS["en"])
    cmap = cmap or HEATMAP_CMAP
    # line_zorder above the imshow (zorder=1) so the pitch markings stay visible on top of the heat.
    pitch, fig, ax = make_pitch(pitch_color="#0e1117", line_zorder=3)
    sub = heat_df[heat_df["team_id"] == team_id].groupby("zone_code")["touches"].sum()
    grid = np.zeros((5, 6))
    for _, z in zone_df.iterrows():
        ci = int(z["zone_code"][1]) - 1
        ri = int(z["zone_code"][3]) - 1
        grid[ri, ci] = sub.get(z["zone_code"], 0)
    im = ax.imshow(grid, extent=[0, 105, 0, 68], origin="lower", cmap=cmap,
                    alpha=0.85, aspect="auto", zorder=1, interpolation="bicubic")

    # Overlay the underlying pitch-zone grid so individual zones stay distinguishable.
    x_bounds = sorted(set(zone_df["x_min"]) | set(zone_df["x_max"]))
    y_bounds = sorted(set(zone_df["y_min"]) | set(zone_df["y_max"]))
    for x in x_bounds[1:-1]:
        ax.plot([x, x], [0, 68], color="#e8ecf1", alpha=0.25, lw=0.6, zorder=2)
    for y in y_bounds[1:-1]:
        ax.plot([0, 105], [y, y], color="#e8ecf1", alpha=0.25, lw=0.6, zorder=2)

    # Mark defence / midfield / attack thirds (attacking direction is toward x=105).
    x_min, x_max = x_bounds[0], x_bounds[-1]
    third1 = x_min + (x_max - x_min) / 3
    third2 = x_min + 2 * (x_max - x_min) / 3
    for x in (third1, third2):
        ax.plot([x, x], [0, 68], color="#f5f7fa", alpha=0.6, lw=1.4, zorder=3, linestyle=(0, (4, 3)))
    for xc, label in zip([(x_min + third1) / 2, (third1 + third2) / 2, (third2 + x_max) / 2], L["thirds"]):
        ax.text(xc, 64.2, label, color="#f5f7fa", alpha=0.85, fontsize=8.5, ha="center",
                va="center", fontweight="bold", zorder=4)

    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label=L["touches"])
    return fig


def pass_map(passes_df, team_id, color="#3fbf7f", fail_color="#e0524b", lang="en"):
    L = LABELS.get(lang, LABELS["en"])
    pitch, fig, ax = make_pitch()
    sub = passes_df[passes_df["team_id"] == team_id]
    success = sub[sub["outcome"] == "Successful"]
    fail = sub[sub["outcome"] != "Successful"]
    pitch.lines(fail["origin_x"], fail["origin_y"], fail["destination_x"], fail["destination_y"],
                color=fail_color, lw=1.2, alpha=0.5, linestyle="dashed", ax=ax, zorder=2)
    pitch.lines(success["origin_x"], success["origin_y"], success["destination_x"], success["destination_y"],
                color=color, lw=1.8, alpha=0.8, ax=ax, zorder=3)
    led = success[success["led_to_shot_within_10s"] == "Yes"]
    pitch.scatter(led["destination_x"], led["destination_y"], s=90, color="#f2c14e",
                  edgecolors="white", linewidth=0.6, ax=ax, zorder=4, marker="o")
    ax.set_title(L["pass_map_title"], color="#9aa4b2", fontsize=8, loc="left")
    return fig
