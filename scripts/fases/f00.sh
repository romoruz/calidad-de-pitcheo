#!/usr/bin/env bash
# F0 — Ingesta, limpieza (ADR-002 a 007) y QA por identidades (ROADMAP §4-F0, sufijo §0.3).
# Corre en LOCAL, sobre data/raw/stuff_model_df.parquet (fuera de git, solo lectura).
# Escribe data/interim/pitches.parquet (particionado por year, fuera de git), reports/FASE_00.md
# (Bloque para el orquestador), reports/fase_00.json, docs/figuras/f00/ y reports/logs/f00_<fecha>.log.
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

# (3) F0 sobre los datos reales. Sale con código != 0 si una compuerta (G0.1-G0.8) falla,
#     DESPUÉS de escribir el reporte. Si hay valores "sin regla" no escribe pitches.parquet.
uv run pitcheo f00

echo "F0 lista. Revisa reports/FASE_00.md: Bloque para el orquestador y tabla play_result × pitch_call_h × KorBB."
