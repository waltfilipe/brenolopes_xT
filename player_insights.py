"""Headlines, rating bands and auto-generated insights for public-facing UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

POSITION_GROUP_LABELS: dict[str, str] = {
    "Zagueiros": "zagueiros",
    "Laterais": "laterais",
    "Meio-campistas": "meio-campistas",
    "Extremos": "extremos",
    "Atacantes": "atacantes",
}

INSIGHT_METRICS: tuple[tuple[str, str], ...] = (
    ("impact_passes_p90", "Conduções que mudam o jogo"),
    ("impact_per_pass", "Conduções produtivas"),
    ("phi_p90", "Conduções decisivas"),
    ("dxt_p90", "Progressão com a bola"),
    ("carries_to_box_p90", "Chegadas à área"),
    ("carries_impact_to_box_p90", "Chegadas de impacto à área"),
    ("dribbles_final_third_p90", "Dribles certos no ataque"),
    ("dxt_gt_015_pct", "Conduções de alto avanço"),
)


def _fmt_stat_value(key: str, value) -> str:
    import carries_engine as ce

    return ce.fmt_stat_value(key, value)


def rating_display_score(pass_rating: float | None) -> float | None:
    if pass_rating is None:
        return None
    return float(pass_rating) * 10.0


def rating_band_text(display_score: float | None) -> str:
    if display_score is None:
        return "Sem nota"
    if display_score >= 8.0:
        return "Elite no Brasileirão"
    if display_score >= 7.0:
        return "Acima da média"
    if display_score >= 6.0:
        return "Na média do campeonato"
    return "Abaixo da média"


def _rank_percentile(rank: int, total: int) -> float:
    if total <= 1:
        return 0.5
    return (rank - 1) / (total - 1)


def _position_phrase(player: dict) -> str:
    group = str(player.get("position_group") or "—")
    label = POSITION_GROUP_LABELS.get(group, group.lower())
    return f"{label} do Brasileirão"


def build_rank_line(player: dict, metric_ranks: dict) -> str:
    info = metric_ranks.get("pass_rating")
    if not info:
        return "Comparativo individual (sem grupo elegível)"
    rank = int(info["rank"])
    total = int(info["total"])
    position = _position_phrase(player)
    if rank == 1:
        return f"Líder entre {position}"
    return f"{rank}º entre {total} {position}"


def _metric_rank(player: dict, metric_ranks: dict, key: str) -> tuple[int, int] | None:
    info = metric_ranks.get(key)
    if not info:
        return None
    return int(info["rank"]), int(info["total"])


def build_profile_line(player: dict, metric_ranks: dict) -> str:
    parts: list[str] = []

    impact_rank = _metric_rank(player, metric_ranks, "impact_passes_p90")
    quality_rank = _metric_rank(player, metric_ranks, "impact_per_pass")
    box_rank = _metric_rank(player, metric_ranks, "carries_to_box_p90")
    drib_rank = _metric_rank(player, metric_ranks, "dribbles_final_third_p90")

    if impact_rank and impact_rank[0] <= max(3, impact_rank[1] // 5):
        parts.append("conduz muito com perigo")
    elif quality_rank and quality_rank[0] <= max(3, quality_rank[1] // 5):
        parts.append("conduz com alta qualidade")

    if box_rank and drib_rank:
        box_good = _rank_percentile(box_rank[0], box_rank[1]) <= 0.35
        drib_good = _rank_percentile(drib_rank[0], drib_rank[1]) <= 0.35
        box_weak = _rank_percentile(box_rank[0], box_rank[1]) >= 0.65
        drib_weak = _rank_percentile(drib_rank[0], drib_rank[1]) >= 0.65

        if box_good and drib_weak:
            parts.append("chega bem à área, dribla pouco no ataque")
        elif drib_good and box_weak:
            parts.append("dribla no ataque, chega menos à área")
        elif box_good and drib_good:
            parts.append("chega à área e dribla perto do gol")
        elif box_weak and drib_weak:
            parts.append("menos presença na área e nos dribles no ataque")

    if not parts:
        carries = player.get("carries_total") or 0
        if carries >= 100:
            parts.append("participa bastante com a bola nos pés")
        else:
            parts.append("perfil equilibrado nas conduções")

    return "Perfil: " + ", ".join(parts) + "."


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
        line = f"{short_label}: {value_txt} ({rank}º entre {total})"

        if pct <= 0.20:
            strong.append((pct, f"Forte — {line}"))
        elif pct >= 0.80:
            develop.append((-pct, f"A desenvolver — {line}"))

    insights: list[tuple[str, str]] = []
    for _, text in sorted(strong, key=lambda item: item[0])[:max_items]:
        insights.append(("strong", text))
    remaining = max_items - len(insights)
    if remaining > 0:
        for _, text in sorted(develop, key=lambda item: item[0], reverse=True)[:remaining]:
            insights.append(("develop", text))

    if not insights:
        insights.append(("neutral", "Desempenho equilibrado entre as métricas do grupo."))
    return insights


def build_headline_summary(player: dict, metric_ranks: dict) -> dict[str, str]:
    display = rating_display_score(player.get("pass_rating"))
    display_txt = f"{display:.1f}/10" if display is not None else "—"
    return {
        "score": display_txt,
        "band": rating_band_text(display),
        "rank_line": build_rank_line(player, metric_ranks),
        "profile": build_profile_line(player, metric_ranks),
    }
