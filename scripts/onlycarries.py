#!/usr/bin/env python3
"""Atalho para fetch_sofascore_carries_dribbles.py (conduções + dribles com coordenadas)."""

from __future__ import annotations

import sys

print("[onlycarries] iniciando …", flush=True)

try:
    from fetch_sofascore_carries_dribbles import main
except ImportError as exc:
    print(
        "\nERRO: dependências ou módulos locais ausentes.\n"
        "  pip install -r requirements-sofascore.txt\n"
        "Arquivos esperados em scripts/:\n"
        "  onlycarries.py\n"
        "  fetch_sofascore_carries_dribbles.py\n"
        "  sofascore_positions.py\n",
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(1) from exc

if __name__ == "__main__":
    raise SystemExit(main())
