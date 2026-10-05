#!/usr/bin/env bash
# F0.0 — Inspección de los tres formatos crudos (ROADMAP §4-F0.0, sufijo §0.3).
# Corre en LOCAL, sobre data/raw/ (fuera de git). Escribe reporte, .json y log.
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

# (3) Inspección sobre los datos reales. El comando escribe:
#     reports/FASE_00_0.md, reports/fase_00_0.json y reports/logs/f00_0_<fecha>.log,
#     y sale con código != 0 si una compuerta (G00.1-G00.3) falla.
uv run pitcheo f00_0

echo "F0.0 lista. Revisa reports/FASE_00_0.md (Bloque para el orquestador)."
