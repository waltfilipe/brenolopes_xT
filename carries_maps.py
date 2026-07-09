"""Impact carry & dribble maps (StatsBomb pitch layout)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle
from mplsoccer import Pitch

FIG_W, FIG_H = 10.0, 6.67
FIG_DPI = 320
FIG_W_COMPACT, FIG_H_COMPACT = 7.2, 4.8
FIG_DPI_COMPACT = 300
MAP_REF_WIDTH = 10.0
FIELD_X, FIELD_Y = 120.0, 80.0
PASS_DEST_HEATMAP_COLS = 12
PASS_DEST_HEATMAP_ROWS = 8
TYPICAL_IMPACT_GRID_COLS = 10
TYPICAL_IMPACT_GRID_ROWS = 6
MAX_TYPICAL_IMPACT_VECTORS = 10
ARROW_WIDTH = 0.75
ARROW_HEADWIDTH = 1.15
ARROW_HEADLENGTH = 1.15
ARROW_ALPHA_EMPH = 0.82
PASS_START_MARKER_SIZE = 7

COLOR_CARRY = "#94a3b8"
COLOR_PROGRESSIVE = "#7dd3fc"
COLOR_HIGHLY_PROGRESSIVE = "#fcd34d"
CMAP_PASS_DEST = LinearSegmentedColormap.from_list(
    "pass_dest", ["#1a1a2e", "#1e3a8a", "#3b82f6", "#fbbf24", "#ef4444"]
)


def _map_scale(fig_w: float) -> float:
    return fig_w / MAP_REF_WIDTH


def _base_pitch(*, figsize: tuple[float, float], dpi: int, bg: str = "#1a1a2e"):
    pitch = Pitch(pitch_type="statsbomb", pitch_color=bg, line_color="#ffffff", line_alpha=0.95)
    fig, ax = pitch.draw(figsize=figsize)
    fig.set_facecolor(bg)
    fig.set_dpi(dpi)
    return fig, ax, pitch


def _add_map_legend(ax, handles: list, *, fig_w: float) -> None:
    scale = _map_scale(fig_w)
    leg = ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.01, 0.99),
        frameon=True,
        facecolor="#1a1a2e",
        edgecolor="#444466",
        fontsize=6.0 * scale,
        labelspacing=0.35 * scale,
        borderpad=0.45 * scale,
        handlelength=1.9 * scale,
    )
    for text in leg.get_texts():
        text.set_color("white")
    leg.get_frame().set_alpha(0.90)


def _attack_arrow(fig, *, fig_w: float) -> None:
    scale = _map_scale(fig_w)
    fig.patches.append(
        FancyArrowPatch(
            (0.44, 0.055),
            (0.56, 0.055),
            transform=fig.transFigure,
            arrowstyle="-|>",
            mutation_scale=13 * scale,
            linewidth=1.65 * scale,
            color="#b0bdd0",
        )
    )
    fig.text(
        0.50,
        0.012,
        "Direção de ataque",
        ha="center",
        va="bottom",
        transform=fig.transFigure,
        fontsize=7.5 * scale,
        color="#b0bdd0",
    )


def _finish_map(fig, ax, *, fig_w: float, title: str) -> None:
    scale = _map_scale(fig_w)
    ax.set_title(title, color="white", fontsize=9.0 * scale, pad=8)
    fig.subplots_adjust(left=0.02, right=0.99, top=0.90, bottom=0.14)
    _attack_arrow(fig, fig_w=fig_w)


def _delicate_arrows(pitch, ax, x1, y1, x2, y2, color, scale: float, *, alpha: float) -> None:
    pitch.arrows(
        x1, y1, x2, y2,
        color=color,
        width=ARROW_WIDTH * scale,
        headwidth=ARROW_HEADWIDTH * scale,
        headlength=ARROW_HEADLENGTH * scale,
        ax=ax,
        zorder=3,
        alpha=alpha,
    )


def draw_all_carries_map(
    passes,
    player_name: str,
    match_label: str = "todos os jogos",
    *,
    compact: bool = True,
):
    """All completed ball-carries (start → end arrows)."""
    if compact:
        figsize = (FIG_W_COMPACT, FIG_H_COMPACT)
        dpi = FIG_DPI_COMPACT
    else:
        figsize = (FIG_W, FIG_H)
        dpi = FIG_DPI

    fig_w = figsize[0]
    scale = _map_scale(fig_w)
    subset = passes[passes["has_end"]].copy()
    fig, ax, pitch = _base_pitch(figsize=figsize, dpi=dpi)

    if subset.empty:
        ax.text(60, 40, "Sem conduções", ha="center", va="center", color="white", fontsize=9)
    else:
        for row in subset.itertuples(index=False):
            _delicate_arrows(
                pitch, ax,
                row.x_start, row.y_start, row.x_end, row.y_end,
                COLOR_CARRY, scale, alpha=0.72,
            )
            pitch.scatter(
                row.x_start, row.y_start,
                s=PASS_START_MARKER_SIZE, marker="o", color=COLOR_CARRY,
                edgecolors="white", linewidths=0.3, ax=ax, zorder=6, alpha=0.72,
            )

    legend_handles = [
        Line2D([0], [0], color=COLOR_CARRY, lw=1.4 * scale, label="Condução", alpha=0.80),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_CARRY,
               markersize=4, linestyle="None", label="Origem da condução"),
    ]
    _add_map_legend(ax, legend_handles, fig_w=fig_w)
    _finish_map(fig, ax, fig_w=fig_w, title="Todas as conduções")
    return fig


def draw_impact_pass_map(
    passes,
    player_name: str,
    match_label: str = "todos os jogos",
    *,
    compact: bool = True,
):
    """Impact passes only — same visual language as the legacy pass map."""
    if compact:
        figsize = (FIG_W_COMPACT, FIG_H_COMPACT)
        dpi = FIG_DPI_COMPACT
    else:
        figsize = (FIG_W, FIG_H)
        dpi = FIG_DPI

    fig_w = figsize[0]
    scale = _map_scale(fig_w)
    subset = passes[passes["impact_success"] & passes["has_end"]].copy()
    fig, ax, pitch = _base_pitch(figsize=figsize, dpi=dpi)

    if subset.empty:
        ax.text(60, 40, "Sem conduções de impacto", ha="center", va="center", color="white", fontsize=9)
    else:
        for row in subset.itertuples(index=False):
            is_high = bool(row.high_impact_success)
            color, alpha = (
                (COLOR_HIGHLY_PROGRESSIVE, ARROW_ALPHA_EMPH)
                if is_high
                else (COLOR_PROGRESSIVE, ARROW_ALPHA_EMPH)
            )
            _delicate_arrows(
                pitch, ax,
                row.x_start, row.y_start, row.x_end, row.y_end,
                color, scale, alpha=alpha,
            )
            pitch.scatter(
                row.x_start, row.y_start,
                s=PASS_START_MARKER_SIZE, marker="o", color=color,
                edgecolors="white", linewidths=0.3, ax=ax, zorder=6, alpha=alpha,
            )

    legend_handles = [
        Line2D([0], [0], color=COLOR_PROGRESSIVE, lw=1.4 * scale, label="Impacto", alpha=0.80),
        Line2D([0], [0], color=COLOR_HIGHLY_PROGRESSIVE, lw=1.4 * scale, label="Alto impacto", alpha=0.85),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_PROGRESSIVE,
               markersize=4, linestyle="None", label="Origem"),
    ]
    _add_map_legend(ax, legend_handles, fig_w=fig_w)
    _finish_map(fig, ax, fig_w=fig_w, title="Conduções de impacto")
    return fig


def _typical_impact_vectors(
    subset,
    *,
    max_vectors: int = MAX_TYPICAL_IMPACT_VECTORS,
    grid_cols: int = TYPICAL_IMPACT_GRID_COLS,
    grid_rows: int = TYPICAL_IMPACT_GRID_ROWS,
) -> list[dict]:
    """Cluster impact carries by coarse start/end bins; return the most frequent patterns."""
    if subset is None or subset.empty:
        return []

    x_bins = np.linspace(0.0, FIELD_X, grid_cols + 1)
    y_bins = np.linspace(0.0, FIELD_Y, grid_rows + 1)
    clusters: dict[tuple[int, int, int, int], list] = {}

    for row in subset.itertuples(index=False):
        sx = int(np.clip(np.digitize(row.x_start, x_bins, right=True) - 1, 0, grid_cols - 1))
        sy = int(np.clip(np.digitize(row.y_start, y_bins, right=True) - 1, 0, grid_rows - 1))
        ex = int(np.clip(np.digitize(row.x_end, x_bins, right=True) - 1, 0, grid_cols - 1))
        ey = int(np.clip(np.digitize(row.y_end, y_bins, right=True) - 1, 0, grid_rows - 1))
        clusters.setdefault((sx, sy, ex, ey), []).append(row)

    ordered = sorted(clusters.values(), key=len, reverse=True)[:max_vectors]
    vectors: list[dict] = []
    for rows in ordered:
        high_count = sum(bool(getattr(r, "high_impact_success", False)) for r in rows)
        vectors.append({
            "x_start": float(np.median([r.x_start for r in rows])),
            "y_start": float(np.median([r.y_start for r in rows])),
            "x_end": float(np.median([r.x_end for r in rows])),
            "y_end": float(np.median([r.y_end for r in rows])),
            "count": len(rows),
            "high_impact": high_count >= len(rows) / 2,
        })
    return vectors


def draw_typical_impact_pass_map(
    passes,
    player_name: str,
    match_label: str = "todos os jogos",
    *,
    max_vectors: int = MAX_TYPICAL_IMPACT_VECTORS,
    compact: bool = True,
):
    """Representative impact-carry vectors — most common binned start→end patterns."""
    if compact:
        figsize = (FIG_W_COMPACT, FIG_H_COMPACT)
        dpi = FIG_DPI_COMPACT
    else:
        figsize = (FIG_W, FIG_H)
        dpi = FIG_DPI

    fig_w = figsize[0]
    scale = _map_scale(fig_w)
    subset = passes[passes["impact_success"] & passes["has_end"]].copy()
    vectors = _typical_impact_vectors(subset, max_vectors=max_vectors)
    fig, ax, pitch = _base_pitch(figsize=figsize, dpi=dpi)

    if not vectors:
        ax.text(60, 40, "Sem conduções de impacto", ha="center", va="center", color="white", fontsize=9)
    else:
        max_count = max(v["count"] for v in vectors)
        for vector in vectors:
            is_high = bool(vector["high_impact"])
            color = COLOR_HIGHLY_PROGRESSIVE if is_high else COLOR_PROGRESSIVE
            freq = vector["count"] / max_count
            alpha = 0.55 + 0.35 * freq
            width_scale = 0.85 + 0.35 * freq
            _delicate_arrows(
                pitch, ax,
                vector["x_start"], vector["y_start"], vector["x_end"], vector["y_end"],
                color, scale * width_scale, alpha=alpha,
            )
            pitch.scatter(
                vector["x_start"], vector["y_start"],
                s=PASS_START_MARKER_SIZE + 2 * freq, marker="o", color=color,
                edgecolors="white", linewidths=0.35, ax=ax, zorder=6, alpha=alpha,
            )

    legend_handles = [
        Line2D([0], [0], color=COLOR_PROGRESSIVE, lw=1.4 * scale, label="Padrão frequente", alpha=0.80),
        Line2D([0], [0], color=COLOR_HIGHLY_PROGRESSIVE, lw=1.4 * scale, label="Padrão de alto impacto", alpha=0.85),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_PROGRESSIVE,
               markersize=4, linestyle="None", label="Origem típica"),
    ]
    _add_map_legend(ax, legend_handles, fig_w=fig_w)
    _finish_map(fig, ax, fig_w=fig_w, title="Padrões típicos de condução de impacto")
    return fig


COLOR_DRIBBLE_OK = "#34d399"
COLOR_DRIBBLE_FAIL = "#f87171"


def draw_dribble_map(
    dribbles,
    player_name: str,
    match_label: str = "todos os jogos",
    *,
    compact: bool = True,
):
    """Dribble attempt locations (start coordinates only)."""
    if compact:
        figsize = (FIG_W_COMPACT, FIG_H_COMPACT)
        dpi = FIG_DPI_COMPACT
    else:
        figsize = (FIG_W, FIG_H)
        dpi = FIG_DPI

    fig_w = figsize[0]
    scale = _map_scale(fig_w)
    fig, ax, pitch = _base_pitch(figsize=figsize, dpi=dpi)

    if dribbles is None or dribbles.empty:
        ax.text(60, 40, "Sem dribles", ha="center", va="center", color="white", fontsize=9)
    else:
        ok = dribbles[dribbles["is_success"]]
        fail = dribbles[~dribbles["is_success"]]
        if not ok.empty:
            pitch.scatter(
                ok["x_start"], ok["y_start"],
                s=28, marker="o", color=COLOR_DRIBBLE_OK,
                edgecolors="white", linewidths=0.35, ax=ax, zorder=5, alpha=0.85,
            )
        if not fail.empty:
            pitch.scatter(
                fail["x_start"], fail["y_start"],
                s=28, marker="x", color=COLOR_DRIBBLE_FAIL,
                linewidths=1.0, ax=ax, zorder=5, alpha=0.85,
            )

    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_DRIBBLE_OK,
               markersize=5, linestyle="None", label="Drible certo"),
        Line2D([0], [0], marker="x", color=COLOR_DRIBBLE_FAIL, markersize=5,
               linestyle="None", label="Drible falho"),
    ]
    _add_map_legend(ax, legend_handles, fig_w=fig_w)
    _finish_map(fig, ax, fig_w=fig_w, title="Dribles")
    return fig


def draw_pass_destination_heatmap(
    passes,
    player_name: str,
    match_label: str = "todos os jogos",
    *,
    compact: bool = True,
):
    """12×8 heatmap of completed impact pass end locations."""
    if compact:
        figsize = (FIG_W_COMPACT, FIG_H_COMPACT)
        dpi = FIG_DPI_COMPACT
    else:
        figsize = (FIG_W, FIG_H)
        dpi = FIG_DPI

    fig_w = figsize[0]
    scale = _map_scale(fig_w)
    completed = passes[passes["impact_success"] & passes["has_end"]].copy()
    fig, ax, pitch = _base_pitch(figsize=figsize, dpi=dpi)

    x_bins = np.linspace(0.0, FIELD_X, PASS_DEST_HEATMAP_COLS + 1)
    y_bins = np.linspace(0.0, FIELD_Y, PASS_DEST_HEATMAP_ROWS + 1)
    grid = np.zeros((PASS_DEST_HEATMAP_ROWS, PASS_DEST_HEATMAP_COLS), dtype=float)

    if not completed.empty:
        x_idx = np.clip(
            np.digitize(completed["x_end"].to_numpy(), x_bins, right=True) - 1,
            0,
            PASS_DEST_HEATMAP_COLS - 1,
        )
        y_idx = np.clip(
            np.digitize(completed["y_end"].to_numpy(), y_bins, right=True) - 1,
            0,
            PASS_DEST_HEATMAP_ROWS - 1,
        )
        for ix, iy in zip(x_idx, y_idx):
            grid[iy, ix] += 1.0

    vmax = max(float(grid.max()), 1.0)
    norm = Normalize(vmin=0.0, vmax=vmax)

    for iy in range(PASS_DEST_HEATMAP_ROWS):
        for ix in range(PASS_DEST_HEATMAP_COLS):
            value = float(grid[iy, ix])
            x0, x1 = x_bins[ix], x_bins[ix + 1]
            y0, y1 = y_bins[iy], y_bins[iy + 1]
            ax.add_patch(
                Rectangle(
                    (x0, y0), x1 - x0, y1 - y0,
                    facecolor=CMAP_PASS_DEST(norm(value)),
                    edgecolor=(1, 1, 1, 0.12),
                    linewidth=0.25,
                    alpha=0.94,
                    zorder=2,
                )
            )

    pitch.draw(ax=ax)
    sm = plt.cm.ScalarMappable(cmap=CMAP_PASS_DEST, norm=norm)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.022, pad=0.02, shrink=0.55)
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}" if v == int(v) else f"{v:.1f}"))
    cbar.ax.yaxis.set_tick_params(color="#ffffff", labelsize=6)
    plt.setp(cbar.ax.axes.get_yticklabels(), color="#ffffff")
    cbar.set_label("Conduções impact", color="#c7cdda", fontsize=7 * scale)
    _finish_map(fig, ax, fig_w=fig_w, title="Destino — conduções de impacto")
    return fig
