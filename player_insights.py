"""Headlines, rating bands and auto-generated insights for public-facing UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

POSITION_GROUP_LABELS: dict[str, str] = {
    "Zagueiros": "center-backs",
    "Laterais": "full-backs",
    "Meio-campistas": "midfielders",
    "Wingers": "wingers",
    "Atacantes": "forwards",
}

INSIGHT_METRICS: tuple[tuple[str, str], ...] = (
    ("impact_passes_p90", "Threat Carries"),
    ("phi_p90", "High-Threat Carries"),
    ("dxt_p90", "Carry Threat"),
    ("carries_to_box_p90", "Box Entries"),
    ("carries_impact_to_box_p90", "Threat Box Entries"),
    ("dribbles_final_third_p90", "Successful Dribbles"),
    ("dxt_gt_015_pct", "% High-Threat Carries"),
)


def _fmt_stat_value(key: str, value) -> str:
    import carries_engine as ce

    return ce.fmt_stat_value(key, value)


def rating_display_score(pass_rating: float | None) -> float | None:
    if pass_rating is None:
        return None
    return float(pass_rating) * 10.0


def rating_band_text(
    display_score: float | None,
    *,
    rank: int | None = None,
    total: int | None = None,
) -> str:
    """Label aligned with position in the peer group (rank), not raw score alone."""
    if rank is not None and total is not None and total > 1:
        t = (rank - 1) / (total - 1)
        if t <= 0.10:
            return "Elite in the league"
        if t <= 0.45:
            return "Above average"
        if t <= 0.72:
            return "League average"
        return "Below average"
    if display_score is None:
        return "No rating"
    if display_score >= 8.0:
        return "Elite in the league"
    if display_score >= 7.0:
        return "Above average"
    if display_score >= 6.0:
        return "League average"
    return "Below average"


def _rank_percentile(rank: int, total: int) -> float:
    if total <= 1:
        return 0.5
    return (rank - 1) / (total - 1)


def _position_phrase(player: dict) -> str:
    group = str(player.get("position_group") or "—")
    label = POSITION_GROUP_LABELS.get(group, group.lower())
    return f"{label} in the league"


def build_rank_line(player: dict, metric_ranks: dict) -> str:
    info = metric_ranks.get("pass_rating")
    if not info:
        return "Individual comparison (no eligible peer group)"
    rank = int(info["rank"])
    total = int(info["total"])
    position = _position_phrase(player)
    if rank == 1:
        return f"Leader among {position}"
    return f"{rank}th of {total} {position}"


def _metric_rank(player: dict, metric_ranks: dict, key: str) -> tuple[int, int] | None:
    info = metric_ranks.get(key)
    if not info:
        return None
    return int(info["rank"]), int(info["total"])


def build_profile_line(player: dict, metric_ranks: dict) -> str:
    parts: list[str] = []

    impact_rank = _metric_rank(player, metric_ranks, "impact_passes_p90")
    quality_rank = _metric_rank(player, metric_ranks, "dxt_gt_015_pct")
    box_rank = _metric_rank(player, metric_ranks, "carries_to_box_p90")
    drib_rank = _metric_rank(player, metric_ranks, "dribbles_final_third_p90")

    if impact_rank and impact_rank[0] <= max(3, impact_rank[1] // 5):
        parts.append("carries with high threat")
    elif quality_rank and quality_rank[0] <= max(3, quality_rank[1] // 5):
        parts.append("high carry effectiveness")

    if box_rank and drib_rank:
        box_good = _rank_percentile(box_rank[0], box_rank[1]) <= 0.35
        drib_good = _rank_percentile(drib_rank[0], drib_rank[1]) <= 0.35
        box_weak = _rank_percentile(box_rank[0], box_rank[1]) >= 0.65
        drib_weak = _rank_percentile(drib_rank[0], drib_rank[1]) >= 0.65

        if box_good and drib_weak:
            parts.append("reaches the box well, dribbles less in attack")
        elif drib_good and box_weak:
            parts.append("dribbles in attack, reaches the box less")
        elif box_good and drib_good:
            parts.append("reaches the box and dribbles near goal")
        elif box_weak and drib_weak:
            parts.append("less presence in the box and in attacking dribbles")

    if not parts:
        carries = player.get("carries_total") or 0
        if carries >= 100:
            parts.append("high involvement in possession")
        else:
            parts.append("balanced carry profile")

    return "Profile: " + ", ".join(parts) + "."


def build_player_insights(player: dict, metric_ranks: dict, *, max_items: int = 3) -> list[tuple[str, str]]:
    """Return (kind, text) where kind is strong | develop | neutral."""
    strong: list[tuple[float, str]] = []
    develop: list[tuple[float, str]] = []

    for key, short_label in INSIGHT_METRICS:
        info = metric_ranks.get(key)
        if not info:
            continue
        rank = int(info["rank"])
        total = int(info["total"])
        if total <= 1:
            continue
        pct = _rank_percentile(rank, total)
        value_txt = _fmt_stat_value(key, player.get(key))
        line = f"{short_label}: {value_txt} ({rank}th of {total})"

        if pct <= 0.20:
            strong.append((pct, f"Strength — {line}"))
        elif pct >= 0.80:
            develop.append((-pct, f"To develop — {line}"))

    insights: list[tuple[str, str]] = []
    for _, text in sorted(strong, key=lambda item: item[0])[:max_items]:
        insights.append(("strong", text))
    remaining = max_items - len(insights)
    if remaining > 0:
        for _, text in sorted(develop, key=lambda item: item[0], reverse=True)[:remaining]:
            insights.append(("develop", text))

    if not insights:
        insights.append(("neutral", "Balanced performance across group metrics."))
    return insights


def build_headline_summary(player: dict, metric_ranks: dict) -> dict[str, str]:
    display = rating_display_score(player.get("pass_rating"))
    display_txt = f"{display:.1f}/10" if display is not None else "—"
    rank_info = metric_ranks.get("pass_rating")
    rank = int(rank_info["rank"]) if rank_info else None
    total = int(rank_info["total"]) if rank_info else None
    return {
        "score": display_txt,
        "band": rating_band_text(display, rank=rank, total=total),
        "rank_line": build_rank_line(player, metric_ranks),
        "profile": build_profile_line(player, metric_ranks),
    }
