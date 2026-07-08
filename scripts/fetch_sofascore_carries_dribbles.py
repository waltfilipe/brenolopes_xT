#!/usr/bin/env python3
"""Download **ball-carries** and **dribbles** coordinates from SofaScore.

Por partida: ``lineups`` + um ``rating-breakdown`` por jogador que entrou.
Extrai somente as categorias ``ball-carries`` e ``dribbles`` (ignora passes e
ações defensivas).

Saída compatível com o schema de eventos do ecossistema passes_xTh / xT:

- ``position_raw`` — código SofaScore da escalação (D, M, DL, AMC, …)
- ``position`` — código resolvido (LB, CAM, RW, …) via ``resolve_match_positions``

Exemplo::

    pip install -r requirements-sofascore.txt
    python -u scripts/onlycarries.py \\
        --url "https://www.sofascore.com/football/tournament/brazil/brasileirao-serie-a/325#id:87678" \\
        --output-dir "./carries2026" \\
        --consolidated-only \\
        --resume \\
        --rate-limit 1.0

    # Copiar consolidado para a raiz do app
    python -u scripts/onlycarries.py ... --copy-season-to-root --season-filename season_carries_dribbles.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

print("[onlycarries] carregando módulos locais …", flush=True)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
for _path in (SCRIPT_DIR, ROOT):
    _entry = str(_path)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from sofascore_positions import resolve_match_positions  # noqa: E402

DEFAULT_OUT = ROOT / "data" / "sofascore"

# (category CSV, ActionStream attribute, allowed eventActionType values)
EXTRACTION_BUCKETS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("ball-carries", "ball_carries", frozenset({"ball-carry"})),
    ("dribbles", "dribbles", frozenset({"dribble"})),
)

ACTION_COLUMNS = [
    "category",
    "eventActionType",
    "isHome",
    "outcome",
    "keypass",
    "isLongBall",
    "start_x",
    "start_y",
    "end_x",
    "end_y",
    "player_id",
    "player_name",
    "position_raw",
    "position",
    "event_id",
    "home_team",
    "away_team",
    "match_date",
]


def parse_tournament_url(url: str) -> tuple[int, int]:
    url = url.strip()
    if "#id:" not in url:
        raise ValueError(
            "A URL precisa do fragmento da temporada, ex.: "
            "'.../brasileirao-serie-a/325#id:87678'"
        )
    path_part, frag = url.split("#id:", 1)
    season_id = int(frag.split("&")[0].split("/")[0].strip())
    path_clean = path_part.rstrip("/").split("?")[0]
    tournament_match = re.search(r"/(\d+)$", path_clean)
    if not tournament_match:
        raise ValueError(f"Não foi possível ler o tournament id em: {path_part}")
    return int(tournament_match.group(1)), season_id


def load_done(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def save_done(path: Path, done: set[int]) -> None:
    path.write_text(json.dumps(sorted(done), indent=2), encoding="utf-8")


def _resolve_proxies(proxy_url: str | None) -> dict[str, str] | None:
    url = (
        proxy_url
        or os.environ.get("TACOSCORE_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
    )
    if not url:
        return None
    return {"https": url, "http": url}


def _proxy_log_label(proxies: dict[str, str]) -> str:
    url = proxies.get("https", "")
    if "@" in url:
        return url.split("@", 1)[1]
    return url


def _log(message: str = "") -> None:
    print(message, flush=True)


def list_finished_matches_verbose(client, tournament_id: int, season_id: int):
    _log("  Conectando ao SofaScore (1ª requisição — pode demorar até 30s) …")
    rounds = client.tournament_rounds(tournament_id, season_id)
    total_rounds = len(rounds.rounds)
    _log(f"  {total_rounds} rodadas — consultando SofaScore …")

    matches = []
    seen: set[int] = set()
    finished_in_round = 0

    for idx, round_info in enumerate(rounds.rounds, start=1):
        round_label = round_info.slug or f"rodada {round_info.round}"
        _log(f"  · [{idx}/{total_rounds}] {round_label} …")
        match_list = client.round_events(
            tournament_id, season_id, round_info.round, round_info.slug
        )
        round_finished = 0
        for summary in match_list.events:
            if summary.event_id in seen:
                continue
            seen.add(summary.event_id)
            if summary.is_finished and summary.has_player_statistics:
                matches.append(summary)
                round_finished += 1
                _log(
                    f"      + {summary.event_id}  {summary.start_timestamp:%Y-%m-%d}  "
                    f"{summary.home_team.name} {summary.display_score} {summary.away_team.name}"
                )
        finished_in_round += round_finished
        _log(
            f"    → {len(match_list.events)} jogos na rodada · "
            f"{round_finished} finalizados com stats (acumulado: {finished_in_round})"
        )

    matches.sort(key=lambda m: m.start_timestamp)
    return matches


def _median(values: list[float]) -> float:
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _count_target_actions(actions, enabled_categories: frozenset[str]) -> int:
    total = 0
    for category, attr, _ in EXTRACTION_BUCKETS:
        if category not in enabled_categories:
            continue
        total += len(getattr(actions, attr))
    return total


def _iter_target_actions(actions, enabled_categories: frozenset[str]):
    for category, attr, allowed_types in EXTRACTION_BUCKETS:
        if category not in enabled_categories:
            continue
        for action in getattr(actions, attr):
            if action.action_type not in allowed_types:
                continue
            yield category, action


def fetch_match_carries_dribbles(
    client,
    event_id: int,
    match_summary,
    *,
    min_minutes: int = 1,
    enabled_categories: frozenset[str] | None = None,
    verbose: bool = True,
) -> tuple[list[dict], int, int]:
    """Ball-carries e dribbles de uma partida: lineups + rating-breakdown por jogador."""
    from tacoscore.exceptions import NotFoundError

    categories = enabled_categories or frozenset(cat for cat, _, _ in EXTRACTION_BUCKETS)

    if verbose:
        _log("  · baixando escalação …")
    lineups = client.event_lineups(event_id)
    meta = {
        "event_id": event_id,
        "home_team": match_summary.home_team.name,
        "away_team": match_summary.away_team.name,
        "match_date": match_summary.start_timestamp.isoformat(),
    }

    raw_position_by_id: dict[int, str] = {}
    for entry in lineups.all_players():
        raw_position_by_id[entry.player.id] = (
            entry.position_match or entry.player.position or ""
        )

    eligible = [
        entry
        for entry in lineups.all_players()
        if entry.statistics.minutes_played >= min_minutes
    ]
    if verbose:
        label = " + ".join(sorted(categories))
        _log(
            f"  · {len(eligible)} jogadores com ≥{min_minutes} min — "
            f"extraindo {label} …"
        )

    player_actions: dict[int, tuple] = {}
    players_fetched = 0
    for idx, entry in enumerate(eligible, start=1):
        players_fetched += 1
        if verbose:
            _log(f"    [{idx}/{len(eligible)}] {entry.player.name}")
        try:
            actions = client.player_actions(event_id, entry.player.id)
        except NotFoundError:
            if verbose:
                _log("      (sem rating-breakdown)")
            continue
        n_actions = _count_target_actions(actions, categories)
        if n_actions == 0:
            if verbose:
                _log("      (0 ball-carries/dribbles)")
            continue
        player_actions[entry.player.id] = (entry, actions)
        if verbose:
            parts = []
            if "ball-carries" in categories:
                parts.append(f"{len(actions.ball_carries)} conduções")
            if "dribbles" in categories:
                parts.append(f"{len(actions.dribbles)} dribles")
            _log(f"      → {', '.join(parts)}")

    mean_y_by_player: dict[int, float] = {}
    for pid, (_, actions) in player_actions.items():
        ys: list[float] = []
        for category, attr, _ in EXTRACTION_BUCKETS:
            if category not in categories:
                continue
            for action in getattr(actions, attr):
                if action.start_y is not None:
                    ys.append(float(action.start_y))
        if ys:
            mean_y_by_player[pid] = _median(ys)

    position_by_id: dict[int, str] = {}
    for side in (lineups.home, lineups.away):
        side_entries = [
            entry
            for entry in side.players
            if entry.statistics.minutes_played >= min_minutes
            and entry.player.id in player_actions
        ]
        if not side_entries:
            continue
        raw_side = {
            entry.player.id: raw_position_by_id.get(entry.player.id, "")
            for entry in side_entries
        }
        mean_y_side = {
            entry.player.id: mean_y_by_player[entry.player.id]
            for entry in side_entries
            if entry.player.id in mean_y_by_player
        }
        position_by_id.update(
            resolve_match_positions(
                raw_by_player=raw_side,
                mean_y_by_player=mean_y_side,
            )
        )

    rows: list[dict] = []
    players_with_data = 0
    for pid, (entry, actions) in player_actions.items():
        players_with_data += 1
        player_name = entry.player.name
        position_raw = raw_position_by_id.get(pid, "")
        position = position_by_id.get(pid, position_raw)
        for category, action in _iter_target_actions(actions, categories):
            rows.append(
                {
                    "category": category,
                    "eventActionType": action.action_type,
                    "isHome": action.is_home,
                    "outcome": action.outcome,
                    "keypass": action.is_keypass,
                    "isLongBall": "",
                    "start_x": action.start_x,
                    "start_y": action.start_y,
                    "end_x": action.end_x,
                    "end_y": action.end_y,
                    "player_id": pid,
                    "player_name": player_name,
                    "position_raw": position_raw,
                    "position": position,
                    **meta,
                }
            )
    return rows, players_with_data, players_fetched


def _append_rows_csv(path: Path, rows: list[dict], *, columns: list[str]) -> None:
    if not rows:
        return
    write_header = not path.exists() or path.stat().st_size == 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _read_csv_header(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle), [])


def _validate_season_csv_schema(path: Path) -> None:
    header = _read_csv_header(path)
    if not header:
        return
    missing = [col for col in ACTION_COLUMNS if col not in header]
    if "position_raw" in missing:
        raise SystemExit(
            f"\nERRO: {path} usa schema antigo (sem coluna position_raw).\n"
            "Use outro --season-filename ou remova o CSV e extraia de novo.\n\n"
            f"Colunas esperadas: {', '.join(ACTION_COLUMNS)}"
        )
    if missing:
        raise SystemExit(
            f"\nERRO: {path} está incompleto. Colunas ausentes: {', '.join(missing)}"
        )


def _consolidate_match_files(out_dir: Path, out_name: str = "season_carries_dribbles.csv") -> int:
    import pandas as pd

    frames = [
        pd.read_csv(p) for p in sorted(out_dir.glob("match_*_carries_dribbles.csv"))
    ]
    if not frames:
        return 0
    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_csv(out_dir / out_name, index=False)
    return len(all_df)


def _parse_categories(raw: str | None) -> frozenset[str]:
    valid = {cat for cat, _, _ in EXTRACTION_BUCKETS}
    if not raw:
        return valid
    chosen = {part.strip().lower() for part in raw.split(",") if part.strip()}
    unknown = chosen - valid
    if unknown:
        raise SystemExit(
            f"Categorias inválidas: {', '.join(sorted(unknown))}. "
            f"Válidas: {', '.join(sorted(valid))}"
        )
    return frozenset(chosen)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Baixa ball-carries e dribbles com coordenadas do SofaScore "
            "(rating-breakdown por jogador)."
        )
    )
    parser.add_argument("--url", help="URL do torneio SofaScore com #id:SEASON")
    parser.add_argument("--tournament-id", type=int)
    parser.add_argument("--season-id", type=int)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--categories",
        default=None,
        metavar="LIST",
        help="Categorias a extrair, separadas por vírgula (padrão: ball-carries,dribbles)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        help="Segundos entre chamadas à API (padrão: 2.0)",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        metavar="URL",
        help="Proxy HTTPS (ou TACOSCORE_PROXY / HTTPS_PROXY)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Pular jogos já em done_carries_dribbles.json",
    )
    parser.add_argument(
        "--consolidated-only",
        action="store_true",
        help="Acrescentar cada jogo direto em season_carries_dribbles.csv",
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        help="Ao final, mesclar match_*_carries_dribbles.csv no consolidado",
    )
    parser.add_argument(
        "--copy-season-to-root",
        action="store_true",
        help="Copiar CSV consolidado para a raiz do repositório",
    )
    parser.add_argument(
        "--season-filename",
        default="season_carries_dribbles.csv",
        help="Nome do CSV consolidado (padrão: season_carries_dribbles.csv)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--event-id", type=int, default=None, help="Baixar apenas este jogo")
    parser.add_argument("--list-only", action="store_true", help="Só listar jogos finalizados")
    parser.add_argument(
        "--min-minutes",
        type=int,
        default=1,
        help="Ignorar jogadores com menos minutos (padrão: 1)",
    )
    parser.add_argument(
        "--cooldown-on-error",
        type=float,
        default=120.0,
        help="Pausa após HTTP 403/429 em segundos (padrão: 120)",
    )
    args = parser.parse_args()

    if args.url:
        tournament_id, season_id = parse_tournament_url(args.url)
    elif args.tournament_id is not None and args.season_id is not None:
        tournament_id, season_id = args.tournament_id, args.season_id
    else:
        parser.error("Informe --url ou --tournament-id e --season-id")

    enabled_categories = _parse_categories(args.categories)

    out_dir = args.output_dir or (
        DEFAULT_OUT / f"{tournament_id}_{season_id}_carries_dribbles"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    done_path = out_dir / "done_carries_dribbles.json"
    meta_path = out_dir / "metadata_carries_dribbles.json"
    season_path = out_dir / args.season_filename

    try:
        _log("Carregando tacoscore + curl_cffi (1ª vez pode levar 20–40s) …")
        from tacoscore import TacosScoreClient
        from tacoscore.exceptions import APIError

        _log("Bibliotecas OK.")
    except ImportError:
        print(
            "Instale: pip install -r requirements-sofascore.txt",
            file=sys.stderr,
            flush=True,
        )
        return 1

    proxies = _resolve_proxies(args.proxy)
    if proxies:
        _log(f"Proxy ativo · {_proxy_log_label(proxies)}")
    client = TacosScoreClient(rate_limit_seconds=args.rate_limit, proxies=proxies)

    _log(f"Listando jogos · tournament={tournament_id} season={season_id} …")
    matches = list_finished_matches_verbose(client, tournament_id, season_id)
    if args.event_id is not None:
        matches = [m for m in matches if m.event_id == args.event_id]
        if not matches:
            print(f"Event {args.event_id} não está entre os jogos finalizados.", file=sys.stderr)
            return 1
    elif args.limit:
        matches = matches[: args.limit]

    meta = {
        "mode": "carries_dribbles_only",
        "categories": sorted(enabled_categories),
        "tournament_id": tournament_id,
        "season_id": season_id,
        "listed_at": datetime.now(timezone.utc).isoformat(),
        "n_matches": len(matches),
        "columns": ACTION_COLUMNS,
        "requests_per_match_hint": "1 lineups + 1 rating-breakdown por jogador com minutos",
        "matches": [
            {
                "event_id": m.event_id,
                "date": m.start_timestamp.isoformat(),
                "home": m.home_team.name,
                "away": m.away_team.name,
                "score": m.display_score,
            }
            for m in matches
        ],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n✓ {len(matches)} jogos finalizados → {meta_path}")

    if args.list_only:
        for m in matches:
            _log(f"  {m.event_id}  {m.start_timestamp:%Y-%m-%d}  {m}")
        return 0

    if args.consolidated_only and args.resume and season_path.exists():
        _validate_season_csv_schema(season_path)
        _log(f"Acrescentando em {season_path.name} existente …")

    done = load_done(done_path) if args.resume else set()
    ok = skipped = 0
    failed: list[tuple[int, str]] = []
    total_rows = 0

    for i, summary in enumerate(matches, start=1):
        event_id = summary.event_id
        label = f"{summary.home_team.name} {summary.display_score} {summary.away_team.name}"
        if args.resume and event_id in done:
            skipped += 1
            _log(f"[{i}/{len(matches)}] SKIP · {event_id} · {label}")
            continue

        _log(f"\n[{i}/{len(matches)}] INÍCIO · {event_id} · {label}")
        try:
            rows, with_data, fetched = fetch_match_carries_dribbles(
                client,
                event_id,
                summary,
                min_minutes=args.min_minutes,
                enabled_categories=enabled_categories,
                verbose=True,
            )
            if args.consolidated_only:
                _append_rows_csv(season_path, rows, columns=ACTION_COLUMNS)
            else:
                import pandas as pd

                pd.DataFrame(rows, columns=ACTION_COLUMNS).to_csv(
                    out_dir / f"match_{event_id}_carries_dribbles.csv",
                    index=False,
                )

            done.add(event_id)
            save_done(done_path, done)
            total_rows += len(rows)
            _log(
                f"  ✓ FIM · {len(rows)} ações · "
                f"{with_data}/{fetched} jogadores com dados"
            )
            if len(rows) == 0:
                _log(
                    "  AVISO: rating-breakdown sem ball-carries/dribbles — SofaScore pode "
                    "não expor coordenadas nesta competição/jogo."
                )
            ok += 1
        except APIError as exc:
            msg = f"{type(exc).__name__}: {exc}"
            _log(f"  ERRO: {msg}")
            failed.append((event_id, msg))
            if exc.status_code in (403, 429):
                _log(f"  Pausa {args.cooldown_on_error:.0f}s …")
                time.sleep(args.cooldown_on_error)
            else:
                time.sleep(2.0)
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            _log(f"  ERRO: {msg}")
            failed.append((event_id, msg))
            time.sleep(2.0)

    _log(f"\nConcluído: {ok} baixados, {skipped} pulados, {len(failed)} falhas")
    if args.consolidated_only and season_path.exists():
        _log(f"Temporada: {season_path} ({total_rows:,} ações nesta execução)")

    if args.consolidate and not args.consolidated_only:
        n = _consolidate_match_files(out_dir, out_name=args.season_filename)
        if n:
            _log(f"Consolidado {n} ações → {season_path}")

    if args.copy_season_to_root and season_path.exists():
        import pandas as pd

        dest = ROOT / args.season_filename
        pd.read_csv(season_path).to_csv(dest, index=False)
        _log(f"Copiado → {dest}")

    if failed:
        (out_dir / "failed_carries_dribbles.json").write_text(
            json.dumps([{"event_id": eid, "error": err} for eid, err in failed], indent=2),
            encoding="utf-8",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
