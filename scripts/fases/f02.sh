#!/usr/bin/env bash
# F2 — Densidad del aire por juego desde la trayectoria (ROADMAP §4-F2, sufijo §0.3).
# Corre en LOCAL, sobre data/interim/pitches.parquet (salida de F0, fuera de git).
# Escribe data/interim/densidad_juego.parquet (por juego, fuera de git), reports/FASE_02.md (Bloque para el
# orquestador), reports/fase_02.json, docs/figuras/f2/ y reports/logs/f02_<fecha>.log.
set -euo pipefail

cd "$(dirname "$0")/../.."

# (1) Entorno fuera de la carpeta del repo.
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/calidad-de-pitcheo}"

# Primera vez: crear el entorno. LightGBM necesita Python 3.12 (ROADMAP §6).
if [ ! -d "$UV_PROJECT_ENVIRONMENT" ]; then
  uv python pin 3.12 >/dev/null 2>&1 || true
  uv sync --extra dev
fi

# (2) Pruebas con datos sintéticos: deben pasar antes de tocar datos reales.
uv run pytest -q

# (3) F2 sobre los datos reales. Sale con código != 0 si una compuerta (G2.1-G2.4) falla,
#     DESPUÉS de escribir el reporte. Corre también la sintética con física exacta (G2.1).
uv run pitcheo f02

echo "F2 lista. Revisa reports/FASE_02.md: Bloque para el orquestador, G2.2 (δ̄ por cubeta) y G2.3 (Deming)."
