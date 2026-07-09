"""Ball Carry & Dribble — Brasileirão Série A dashboard."""

from __future__ import annotations

import html
import sys
import unicodedata
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent
for _path in (_APP_ROOT, _APP_ROOT / "scripts_ballcarriers"):
    _entry = str(_path)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import streamlit as st

import carries_engine as ce
from carries_maps import draw_all_carries_map, draw_dribble_map, draw_impact_pass_map, draw_typical_impact_pass_map

DATA_CACHE_VERSION = ce.DATA_CACHE_VERSION
IMPACT_MODEL_DEFAULT = ce.IMPACT_MODEL_DEFAULT
IMPACT_MODEL_LABELS = ce.IMPACT_MODEL_LABELS
ABSOLUTE_METRIC_KEYS = ce.ABSOLUTE_METRIC_KEYS
RELATIVE_METRIC_KEYS = ce.RELATIVE_METRIC_KEYS
GENERAL_CARRIES_DRIBBLES_METRIC_KEYS = ce.GENERAL_CARRIES_DRIBBLES_METRIC_KEYS
build_position_average_players = ce.build_position_average_players
is_position_average_player_id = ce.is_position_average_player_id
IMPACT_MODEL_SELECT_KEY = "impact_model_select"
build_analytics = ce.build_analytics
compute_pass_ratings = ce.compute_pass_ratings
fmt_pct = ce.fmt_pct
fmt_stat_value = ce.fmt_stat_value
load_passes_grouped = ce.load_passes_grouped
load_dribbles_grouped = ce.load_dribbles_grouped
metric_label = ce.metric_label
metric_tooltip = ce.metric_tooltip
rank_to_display_score = ce.rank_to_display_score
score_display_color = ce.score_display_color
rate_player_vs_eligible_pool = ce.rate_player_vs_eligible_pool

from player_insights import POSITION_GROUP_LABELS, build_headline_summary


def fmt_rating_score(pass_rating) -> str:
    if pass_rating is None:
        return "—"
    return f"{float(pass_rating) * 10.0:.1f}"


st.set_page_config(page_title="Ball Carry & Dribble", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.25rem; max-width: 1600px; }
    .player-card {
        background: linear-gradient(160deg, #151b2b 0%, #101522 100%);
        border: 1px solid #2a3550;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.65rem;
    }
    .player-info-card .player-header-stats {
        display: grid;
        grid-template-columns: 1fr;
        gap: 0.5rem;
        justify-content: stretch;
        margin-top: 0.75rem;
    }
    .player-info-card .rating-row { margin-top: 0.75rem; }
    .player-info-card .header-stat strong { font-size: 0.98rem; }
    .header-stat {
        font-size: 0.84rem;
        color: #94a3b8;
        white-space: nowrap;
    }
    .header-stat strong {
        display: block;
        color: #f8fafc;
        font-size: 1.02rem;
        font-weight: 700;
        margin-top: 0.1rem;
    }
    .rating-row {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-bottom: 0;
    }
    .rating-warning-tip {
        position: relative;
        display: inline-flex;
        align-items: center;
    }
    .rating-warning {
        font-size: 1.2rem;
        line-height: 1;
        cursor: help;
        color: #fbbf24;
        filter: drop-shadow(0 0 4px rgba(251, 191, 36, 0.35));
    }
    .player-card h3 { margin: 0 0 0.15rem 0; color: #f1f5f9; font-size: 1.15rem; }
    .headline-block { margin: 0.55rem 0 0.65rem 0; }
    .headline-top {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-bottom: 0.25rem;
    }
    .headline-score {
        color: #f8fafc;
        font-size: 1.35rem;
        font-weight: 800;
    }
    .headline-band {
        color: #93c5fd;
        font-size: 0.88rem;
        font-weight: 700;
    }
    .headline-rank {
        color: #cbd5e1;
        font-size: 0.88rem;
        margin-bottom: 0.35rem;
    }
    .headline-rank-leader {
        color: #c9a227;
        font-weight: 700;
    }
    .metric-rank-sub {
        color: #64748b;
        font-size: 0.74rem;
        font-weight: 600;
        line-height: 1.2;
    }
    .metric-rank-leader {
        color: #c9a227;
        font-weight: 700;
    }
    .cmp-arrow {
        font-size: 1rem;
        font-weight: 800;
        line-height: 1;
    }
    .cmp-up { color: #22c55e; }
    .cmp-down { color: #ef4444; }
    .metric-label-block {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
        min-width: 0;
    }
    .metric-tip {
        position: relative;
        display: inline-flex;
        cursor: help;
        border-bottom: 1px dotted #64748b;
    }
    .metric-tip:hover .rank-tipbox { display: block; }
    .player-card .sub { color: #94a3b8; font-size: 0.85rem; margin-bottom: 0; }
    .player-card .rating-box {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 76px;
        height: 50px;
        padding: 0 12px;
        border-radius: 8px;
        font-size: 1.55rem;
        font-weight: 800;
        margin-bottom: 0;
        border: 1px solid rgba(255,255,255,0.16);
        letter-spacing: 0.02em;
    }
    .metric-line .stat-val {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .metric-line {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.32rem 0;
        border-bottom: 1px solid #1f293f;
        font-size: 0.88rem;
        color: #cbd5e1;
    }
    .metric-line span:last-child { white-space: nowrap; }
    .val-wrap { display: inline-flex; align-items: center; gap: 0.5rem; }
    .rank-badge {
        display: inline-block;
        width: 12px;
        height: 12px;
        min-width: 12px;
        border-radius: 3px;
        flex-shrink: 0;
        border: 1px solid rgba(255,255,255,0.2);
        cursor: help;
    }
    .rank-tip, .rating-tip, .section-rating-tip {
        position: relative;
        display: inline-flex;
    }
    .rank-tipbox, .rating-tipbox {
        display: none;
        position: absolute;
        z-index: 100;
        left: 50%;
        bottom: calc(100% + 6px);
        transform: translateX(-50%);
        background: #111827;
        border: 1px solid #3d4f6f;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 0.72rem;
        font-weight: 700;
        color: #e2e8f0;
        white-space: nowrap;
        box-shadow: 0 8px 20px rgba(0,0,0,.4);
        pointer-events: none;
    }
    .rank-tip:hover .rank-tipbox,
    .rating-tip:hover .rating-tipbox,
    .section-rating-tip:hover .rating-tipbox,
    .rating-warning-tip:hover .rating-tipbox {
        display: block;
    }
    .stat-section-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.6rem;
        margin-top: 0.7rem;
        margin-bottom: 0.25rem;
    }
    .stat-section {
        color: #93c5fd;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .section-rating-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 52px;
        padding: 4px 11px;
        border-radius: 7px;
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        border: 1px solid rgba(255,255,255,0.18);
        white-space: nowrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Ball Carry & Dribble — Brasileirão Série A")

LOCKED_DASHBOARD_PLAYER_NAME = "Breno Lopes"
LOCKED_COMPARISON_AVG_LABEL = "Average - Wingers"

COMPARISON_METRIC_KEYS: tuple[str, ...] = (
    "carries_total",
    "impact_passes",
    "high_impact_passes",
    "impact_carry_avg_distance_m",
    *ABSOLUTE_METRIC_KEYS,
    *RELATIVE_METRIC_KEYS,
    *GENERAL_CARRIES_DRIBBLES_METRIC_KEYS,
)


@st.cache_data(show_spinner=False)
def load_analytics(
    _cache_version: int = DATA_CACHE_VERSION,
    impact_model: str = IMPACT_MODEL_DEFAULT,
):
    return build_analytics(_cache_version, impact_model)


@st.cache_data(show_spinner=False)
def load_carries(
    _cache_version: int = DATA_CACHE_VERSION,
    impact_model: str = IMPACT_MODEL_DEFAULT,
):
    return load_passes_grouped(_cache_version, impact_model)


@st.cache_data(show_spinner=False)
def load_dribbles(
    _cache_version: int = DATA_CACHE_VERSION,
    impact_model: str = IMPACT_MODEL_DEFAULT,
):
    return load_dribbles_grouped(_cache_version, impact_model)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def rank_color(rank: int, total: int) -> str:
    if total <= 0:
        return score_display_color(6.0)
    effective_rank = min(max(rank, 1), total)
    return score_display_color(rank_to_display_score(effective_rank, total))


def rating_value_color(pass_rating: float | None) -> str:
    if pass_rating is None:
        return "#334155"
    return score_display_color(float(pass_rating) * 10.0)


def _player_id_by_name(players: list[dict], name: str) -> str | None:
    for player in players:
        if player.get("player_name") == name:
            return str(player["player_id"])
    return None


def _player_options(
    players: list[dict],
    *,
    position_averages: list[dict] | None = None,
) -> list[tuple[str, str, str, str]]:
    rows = sorted(
        {
            (p["player_id"], p["player_name"], p.get("team", "—"))
            for p in players
            if not is_position_average_player_id(str(p["player_id"]))
        },
        key=lambda x: _norm(x[1]),
    )
    options = [(pid, name, team, f"{name} ({team})") for pid, name, team in rows]
    if position_averages:
        avg_options = [
            (p["player_id"], p["player_name"], p.get("team", "—"), p["player_name"])
            for p in position_averages
        ]
        options = avg_options + options
    return options


def _aggregate_events_for_pool(
    pool: list[dict],
    by_player: dict,
):
    import pandas as pd

    frames = []
    for player in pool:
        pid = str(player["player_id"])
        if is_position_average_player_id(pid):
            continue
        frame = by_player.get(pid)
        if frame is not None and not frame.empty:
            frames.append(frame)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _events_for_player(
    player: dict,
    pool_by_position: dict[str, list[dict]],
    by_player: dict,
):
    if player.get("is_position_average"):
        group = str(player.get("position_group") or "—")
        pool = pool_by_position.get(group, [])
        return _aggregate_events_for_pool(pool, by_player)
    return by_player.get(str(player["player_id"]))


def _rating_warnings_html(player: dict) -> str:
    warnings: list[str] = []
    if not player.get("eligible_minutes", True):
        warnings.append("Under 30% of minutes")
    if not player.get("eligible_passes", True):
        min_carries = player.get("position_min_passes")
        if min_carries is not None:
            min_txt = fmt_stat_value("passes_completed", min_carries)
            warnings.append(f"Under 30% of position carries (min. {min_txt})")
        else:
            warnings.append("Under 30% of position carries")
    return "".join(
        '<span class="rating-warning-tip">'
        '<span class="rating-warning">⚠</span>'
        f'<span class="rating-tipbox">{html.escape(msg)}</span>'
        "</span>"
        for msg in warnings
    )


def _stat_display(player: dict, key: str) -> str:
    if key == "minutes_pct":
        pct = player.get("minutes_pct")
        return fmt_pct(pct * 100.0) if pct is not None else "—"
    return fmt_stat_value(key, player.get(key))


def _badge_text_color(hex_color: str) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return "#1e293b" if lum > 168 else "#f8fafc"


def _label_html(key: str) -> str:
    label = metric_label(key)
    tip = metric_tooltip(key)
    if not tip:
        return html.escape(label)
    return (
        f'<span class="metric-tip">{html.escape(label)}'
        f'<span class="rank-tipbox">{html.escape(tip)}</span></span>'
    )


def _metric_rank_subline(player: dict, metric_ranks: dict, key: str) -> str:
    info = metric_ranks.get(key)
    if not info:
        return ""
    rank = int(info["rank"])
    group = POSITION_GROUP_LABELS.get(str(player.get("position_group") or "—"), str(player.get("position_group") or "—"))
    if rank == 1:
        return f"Leader among {group}"
    return f"{rank}th among {group}"


def _headline_html(player: dict, metric_ranks: dict, *, highlight_leader: bool = False) -> str:
    summary = build_headline_summary(player, metric_ranks)
    warnings = _rating_warnings_html(player)
    rank_line = summary["rank_line"]
    rank_cls = "headline-rank"
    if highlight_leader and rank_line.startswith("Leader among"):
        rank_cls += " headline-rank-leader"
    return (
        '<div class="headline-block">'
        f'<div class="headline-top">'
        f'<span class="headline-score">{html.escape(summary["score"])}</span>'
        f'<span class="headline-band">{html.escape(summary["band"])}</span>'
        f"</div>"
        f'<div class="{rank_cls}">{html.escape(rank_line)}</div>'
        f'{warnings}'
        "</div>"
    )


def _metric_numeric_value(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _comparison_arrow_html(value, peer_value) -> str:
    left = _metric_numeric_value(value)
    right = _metric_numeric_value(peer_value)
    if left is None or right is None:
        return ""
    if left > right:
        return '<span class="cmp-arrow cmp-up" title="Above the other player">↑</span>'
    if left < right:
        return '<span class="cmp-arrow cmp-down" title="Below the other player">↓</span>'
    return ""


def _metric_line_html(
    label: str,
    key: str,
    value: str,
    metric_ranks: dict,
    player: dict,
    *,
    show_rank: bool = True,
    show_rank_subline: bool = True,
    highlight_leader: bool = False,
    use_tooltip_label: bool = True,
    peer: dict | None = None,
) -> str:
    label_html = _label_html(key) if use_tooltip_label else html.escape(label)
    rank_sub = ""
    badge = ""
    if show_rank:
        info = metric_ranks.get(key)
        if info:
            rank = int(info["rank"])
            total = int(info["total"])
            color = rank_color(rank, total)
            badge = (
                f'<span class="rank-tip">'
                f'<span class="rank-badge" style="background:{color}"></span>'
                f'<span class="rank-tipbox">{rank}/{total}</span>'
                f"</span>"
            )
        if show_rank_subline:
            sub = _metric_rank_subline(player, metric_ranks, key)
            if sub:
                sub_cls = "metric-rank-sub"
                if highlight_leader and sub.startswith("Leader among"):
                    sub_cls += " metric-rank-leader"
                rank_sub = f'<div class="{sub_cls}">{html.escape(sub)}</div>'
    label_block = f'<div class="metric-label-block">{label_html}{rank_sub}</div>'
    arrow = _comparison_arrow_html(player.get(key), peer.get(key) if peer else None) if peer else ""
    if peer and not show_rank:
        extras = [part for part in (arrow,) if part]
    else:
        extras = [part for part in (badge, arrow) if part]
    value_html = (
        f'<span class="val-wrap">{"".join(extras)}<span class="stat-val">{html.escape(value)}</span></span>'
        if extras
        else f'<span class="stat-val">{html.escape(value)}</span>'
    )
    return (
        '<div class="metric-line">'
        f"{label_block}"
        f"{value_html}"
        "</div>"
    )


def _section_header_html(title: str, section_key: str, player: dict) -> str:
    section_ratings = player.get("section_ratings") if isinstance(player.get("section_ratings"), dict) else {}
    section_rank_info = player.get("section_rating_ranks") if isinstance(player.get("section_rating_ranks"), dict) else {}
    score = section_ratings.get(section_key)
    pill = ""
    if score is not None:
        txt = fmt_rating_score(score)
        rank_info = section_rank_info.get(section_key)
        if rank_info:
            color = rank_color(int(rank_info["rank"]), int(rank_info["total"]))
            txt_color = _badge_text_color(color)
            rank_txt = f'{int(rank_info["rank"])}/{int(rank_info["total"])}'
            pill = (
                f'<span class="section-rating-tip">'
                f'<span class="section-rating-pill" style="background:{color};color:{txt_color}">'
                f"{html.escape(txt)}</span>"
                f'<span class="rating-tipbox">{rank_txt}</span>'
                f"</span>"
            )
        else:
            pill = f'<span class="section-rating-pill">{html.escape(txt)}</span>'
    return (
        '<div class="stat-section-row">'
        f'<span class="stat-section">{html.escape(title)}</span>'
        f"{pill}"
        "</div>"
    )


def _build_sections_html(
    player: dict,
    metric_ranks: dict,
    sections: list[tuple[str, str | None, tuple[str, ...], bool]],
    *,
    peer: dict | None = None,
    show_rank_subline: bool = True,
    highlight_leader: bool = False,
) -> str:
    parts: list[str] = []
    for title, section_key, keys, show_rank in sections:
        if section_key:
            parts.append(_section_header_html(title, section_key, player))
        else:
            parts.append(
                f'<div class="stat-section-row"><span class="stat-section">{html.escape(title)}</span></div>'
            )
        for key in keys:
            parts.append(
                _metric_line_html(
                    metric_label(key),
                    key,
                    _stat_display(player, key),
                    metric_ranks,
                    player,
                    show_rank=show_rank,
                    show_rank_subline=show_rank_subline,
                    highlight_leader=highlight_leader,
                    peer=peer,
                )
            )
    return "".join(parts)


def _rating_header_html(player: dict, metric_ranks: dict) -> str:
    rating_val = player.get("pass_rating")
    rating_txt = fmt_rating_score(rating_val) if rating_val is not None else "—"
    rating_info = metric_ranks.get("pass_rating")
    is_solo = bool(player.get("rating_is_solo"))

    if rating_info and rating_val is not None:
        r_color = rating_value_color(rating_val)
        r_txt = _badge_text_color(r_color)
        rank_txt = f'{int(rating_info["rank"])}/{int(rating_info["total"])}'
        if is_solo:
            rank_txt += " · individual"
        elif player.get("rating_is_compared"):
            rank_txt += " · vs eligible"
        rating_box = (
            f'<span class="rating-tip">'
            f'<div class="rating-box" style="background:{r_color};color:{r_txt};margin-bottom:0">'
            f"{html.escape(rating_txt)}</div>"
            f'<span class="rating-tipbox">{html.escape(rank_txt)}</span>'
            f"</span>"
        )
    else:
        rating_box = (
            f'<div class="rating-box" style="background:#334155;color:#f8fafc;margin-bottom:0">'
            f"{html.escape(rating_txt)}</div>"
        )

    warnings = _rating_warnings_html(player)
    return f'<div class="rating-row">{rating_box}{warnings}</div>'


def _player_card_html(
    player: dict,
    sections: list[tuple[str, str | None, tuple[str, ...], bool]],
) -> str:
    metric_ranks = player.get("metric_ranks") if isinstance(player.get("metric_ranks"), dict) else {}
    return (
        '<div class="player-card">'
        + _build_sections_html(
            player,
            metric_ranks,
            sections,
            highlight_leader=True,
        )
        + "</div>"
    )


def render_player_layout(player: dict, carries, dribbles) -> None:
    team_label = player.get("team", "—")
    player_name = player["player_name"]
    col_map1, col_map2, col_map3 = st.columns(3, gap="small")

    with col_map1:
        if carries is None or carries.empty:
            st.warning("No carries for this player.")
        else:
            fig_all = draw_all_carries_map(carries, player_name, team_label, compact=False)
            st.pyplot(fig_all, clear_figure=True, use_container_width=True)

    with col_map2:
        if carries is None or carries.empty:
            st.warning("No threat carries for this player.")
        else:
            fig = draw_impact_pass_map(carries, player_name, team_label, compact=False)
            st.pyplot(fig, clear_figure=True, use_container_width=True)

    with col_map3:
        if dribbles is None or dribbles.empty:
            st.info("No dribbles with coordinates for this player.")
        else:
            fig_drib = draw_dribble_map(dribbles, player_name, team_label, compact=False)
            st.pyplot(fig_drib, clear_figure=True, use_container_width=True)

    general_sections: list[tuple[str, str | None, tuple[str, ...], bool]] = [
        (
            "Summary",
            None,
            (
                "minutes",
                "carries_total",
                "minutes_pct",
                "impact_passes",
                "high_impact_passes",
                "dribbles_total",
                "dribble_success_pct",
            ),
            False,
        ),
    ]
    abs_sections: list[tuple[str, str | None, tuple[str, ...], bool]] = [
        ("Carrying Threat (per game)", "metrics_absolute", ABSOLUTE_METRIC_KEYS, True),
    ]
    rel_sections: list[tuple[str, str | None, tuple[str, ...], bool]] = [
        ("Carry Effectiveness", "metrics_relative", RELATIVE_METRIC_KEYS, True),
    ]
    general_carry_dribble_sections: list[tuple[str, str | None, tuple[str, ...], bool]] = [
        (
            "Final Third Threat (PER GAME)",
            "general_carries_dribbles",
            GENERAL_CARRIES_DRIBBLES_METRIC_KEYS,
            True,
        ),
    ]

    metric_ranks = player.get("metric_ranks") if isinstance(player.get("metric_ranks"), dict) else {}
    general_card = (
        '<div class="player-card player-info-card">'
        f"<h3>{html.escape(player['player_name'])}</h3>"
        f'<div class="sub">{html.escape(player.get("team", "—"))} · {html.escape(str(player.get("position", "—")))}</div>'
        f"{_headline_html(player, metric_ranks, highlight_leader=True)}"
        + _build_sections_html(
            player,
            metric_ranks,
            general_sections,
            highlight_leader=True,
        )
        + "</div>"
    )

    col_general, col_abs, col_rel, col_general_cd = st.columns(4, gap="small")
    with col_general:
        st.markdown(general_card, unsafe_allow_html=True)
    with col_abs:
        st.markdown(_player_card_html(player, abs_sections), unsafe_allow_html=True)
    with col_rel:
        st.markdown(_player_card_html(player, rel_sections), unsafe_allow_html=True)
    with col_general_cd:
        st.markdown(_player_card_html(player, general_carry_dribble_sections), unsafe_allow_html=True)


def _resolve_player(
    player: dict,
    pool_by_position: dict[str, list[dict]],
) -> dict:
    resolved = dict(player)
    if resolved.get("is_position_average") or resolved.get("eligible_for_rating"):
        return resolved
    group = str(resolved.get("position_group") or "—")
    return rate_player_vs_eligible_pool(resolved, pool_by_position.get(group, []))


def _comparison_stats_card(player: dict, peer: dict | None = None) -> str:
    metric_ranks = player.get("metric_ranks") if isinstance(player.get("metric_ranks"), dict) else {}
    sections: list[tuple[str, str | None, tuple[str, ...], bool]] = [
        ("Metrics", None, COMPARISON_METRIC_KEYS, False),
    ]
    header = (
        '<div class="player-card player-info-card">'
        f"<h3>{html.escape(player['player_name'])}</h3>"
        f'<div class="sub">{html.escape(player.get("team", "—"))} · '
        f'{html.escape(str(player.get("position", "—")))}</div>'
        f"{_headline_html(player, metric_ranks)}"
    )
    body = _build_sections_html(
        player,
        metric_ranks,
        sections,
        peer=peer,
        show_rank_subline=False,
    )
    return header + body + "</div>"


def render_comparison_section(
    all_players: list[dict],
    players_by_id: dict[str, dict],
    pool_by_position: dict[str, list[dict]],
    position_averages: list[dict],
    carries_by_player: dict,
) -> None:
    st.subheader("Side-by-side comparison")

    breno_id = _player_id_by_name(all_players, LOCKED_DASHBOARD_PLAYER_NAME)
    avg_player = next(
        (p for p in position_averages if p.get("player_name") == LOCKED_COMPARISON_AVG_LABEL),
        None,
    )
    if not avg_player or not breno_id or breno_id not in players_by_id:
        st.error("Could not load fixed comparison (Average - Wingers vs Breno Lopes).")
        return

    resolved: list[tuple[str, dict]] = [
        (
            str(avg_player["player_id"]),
            _resolve_player(dict(avg_player), pool_by_position),
        ),
        (
            str(breno_id),
            _resolve_player(dict(players_by_id[breno_id]), pool_by_position),
        ),
    ]

    col_left, col_right = st.columns(2, gap="medium")
    for col, (player_id, player), (_, peer) in zip(
        (col_left, col_right),
        resolved,
        (resolved[1], resolved[0]),
    ):
        carries = _events_for_player(player, pool_by_position, carries_by_player)
        team_label = player.get("team", "—")

        with col:
            if carries is None or carries.empty:
                st.warning(f"No threat carries for {player['player_name']}.")
            elif player.get("is_position_average"):
                fig = draw_typical_impact_pass_map(
                    carries,
                    player["player_name"],
                    team_label,
                    compact=False,
                    high_res=True,
                )
                st.pyplot(fig, clear_figure=True, use_container_width=True)
            else:
                fig = draw_impact_pass_map(
                    carries,
                    player["player_name"],
                    team_label,
                    compact=False,
                    high_res=True,
                )
                st.pyplot(fig, clear_figure=True, use_container_width=True)
            st.markdown(_comparison_stats_card(player, peer), unsafe_allow_html=True)


def render_map_section(
    all_players: list[dict],
    players_by_id: dict[str, dict],
    pool_by_position: dict[str, list[dict]],
    carries_by_player: dict,
    dribbles_by_player: dict,
) -> None:
    st.subheader("Maps")

    breno_id = _player_id_by_name(all_players, LOCKED_DASHBOARD_PLAYER_NAME)
    if not breno_id or breno_id not in players_by_id:
        st.error(f"Player {LOCKED_DASHBOARD_PLAYER_NAME} not found in the data.")
        return

    player_id = breno_id
    st.session_state["map_player_id"] = player_id
    player = dict(players_by_id[player_id])
    if not player.get("eligible_for_rating"):
        group = str(player.get("position_group") or "—")
        player = rate_player_vs_eligible_pool(player, pool_by_position.get(group, []))
    carries = carries_by_player.get(player_id)
    dribbles = dribbles_by_player.get(player_id)

    render_player_layout(player, carries, dribbles)


def render_impact_model_selector() -> str:
    options = list(IMPACT_MODEL_LABELS.keys())
    with st.sidebar:
        st.markdown("### Impact model")
        impact_model = st.selectbox(
            "Classification",
            options=options,
            format_func=lambda key: IMPACT_MODEL_LABELS[key],
            key=IMPACT_MODEL_SELECT_KEY,
            label_visibility="collapsed",
            help=(
                "Current: relative gain ΔxT/(1−xT) with thresholds 0.30 / 0.62. "
                "Option 1 + short lane: distance-adjusted thresholds and short final-third carries."
            ),
        )
    return impact_model


def main() -> None:
    impact_model = render_impact_model_selector()

    with st.spinner("Loading data…"):
        _, all_players = load_analytics(impact_model=impact_model)
        carries_by_player = load_carries(impact_model=impact_model)
        dribbles_by_player = load_dribbles(impact_model=impact_model)

    _, players_by_id, pool_by_position = compute_pass_ratings(all_players)
    position_averages = build_position_average_players(pool_by_position)
    for avg_player in position_averages:
        players_by_id[avg_player["player_id"]] = avg_player

    tab_dashboard, tab_comparison = st.tabs(["Dashboard", "Comparison"])

    with tab_dashboard:
        render_map_section(
            all_players,
            players_by_id,
            pool_by_position,
            carries_by_player,
            dribbles_by_player,
        )

    with tab_comparison:
        render_comparison_section(
            all_players,
            players_by_id,
            pool_by_position,
            position_averages,
            carries_by_player,
        )


if __name__ == "__main__":
    main()
