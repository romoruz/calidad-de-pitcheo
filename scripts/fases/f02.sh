#!/usr/bin/env bash
# F2 — Densidad del aire por juego desde la trayectoria (ROADMAP §4-F2, sufijo §0.3), por etapas (ADR-019).
# Corre en LOCAL, sobre data/interim/pitches.parquet (salida de F0, fuera de git).
#
#   bash scripts/fases/f02.sh [--etapa pruebas|escala|sintetica|real|todo] [--cpu-max 300] [--n-jobs 3]
#                             [--sin-cache] [--commit]
#
#   pruebas    pytest -q (sintético; deben pasar antes de tocar datos reales).
#   escala     ≈635 k lanzamientos sintéticos: tiempo y RAM pico (reports/f02_escala.json). En `todo` se salta si el archivo
#              existe con el mismo hash de código.
#   sintetica  estudio de simulación de G2.1, G2.3b y cobertura de G2.4 (R = 30, semillas 211-240; reports/f02_sintetica.json).
#              Usa la caché reports/cache/f02_sint/ (fuera de git) salvo --sin-cache.
#   real       análisis sobre los datos reales + compuertas (lee reports/f02_sintetica.json; falla si falta o está vieja).
#   todo       pruebas → escala → sintetica → real (default).
#
# Pensado para una laptop de 4 núcleos físicos / 8 hilos que debe quedar usable: `nice -n 10 ionice -c3`, joblib con
# n_jobs=3 (nunca -1), BLAS a 1 hilo en cada worker y hasta 4 en el proceso principal, y --cpu-max N (% de un núcleo; 300 =
# 3 núcleos) vía `systemd-run --user --scope -p CPUQuota=N%` si está disponible. Mide tiempo, RAM pico (con los hijos) y CPU %
# promedio por etapa en reports/f02_recursos.json (meta: CPU promedio <= 75 % del equipo).
#
# Señales: Ctrl-C / SIGTERM terminan los workers de loky y la etapa queda `interrumpida`; con --commit NO se commitea si
# alguna etapa fue interrumpida o falló con error. Una compuerta fallida (salida 2) SÍ se commitea: el reporte es el entregable.
# Código de salida: 0 todo bien · 2 alguna compuerta falló / fase detenida · 130 interrumpido · otro: error.
set -uo pipefail

cd "$(dirname "$0")/../.."

ETAPA=todo; CPU_MAX=""; N_JOBS=""; SIN_CACHE=0; COMMIT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --etapa) ETAPA="$2"; shift 2 ;;
    --cpu-max) CPU_MAX="$2"; shift 2 ;;
    --n-jobs) N_JOBS="$2"; shift 2 ;;
    --sin-cache) SIN_CACHE=1; shift ;;
    --commit) COMMIT=1; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "argumento desconocido: $1" >&2; exit 64 ;;
  esac
done
case "$ETAPA" in pruebas|escala|sintetica|real|todo) ;; *) echo "--etapa inválida: $ETAPA" >&2; exit 64 ;; esac

# (1) Entorno fuera de la carpeta del repo.
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/calidad-de-pitcheo}"
# Primera vez: crear el entorno. LightGBM necesita Python 3.12 (ROADMAP §6).
if [ ! -d "$UV_PROJECT_ENVIRONMENT" ]; then
  uv python pin 3.12 >/dev/null 2>&1 || true
fi
uv sync --extra dev >/dev/null

# (2) BLAS/OpenMP a 1 hilo en los workers (se hereda del entorno); el proceso principal sube a 4 con threadpoolctl.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

# (3) Prioridad baja y, si se pidió, tope de CPU.
PRE=()
if command -v ionice >/dev/null 2>&1; then PRE=(ionice -c3 ${PRE[@]+"${PRE[@]}"}); fi
if command -v nice >/dev/null 2>&1; then PRE=(nice -n 10 ${PRE[@]+"${PRE[@]}"}); fi
if [ -n "$CPU_MAX" ]; then
  if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope -q -p "CPUQuota=${CPU_MAX}%" true >/dev/null 2>&1; then
    PRE=(systemd-run --user --scope -q -p "CPUQuota=${CPU_MAX}%" ${PRE[@]+"${PRE[@]}"})
    echo "[f02] tope de CPU: ${CPU_MAX} % de un núcleo (systemd-run --user --scope)"
  else
    echo "[f02] AVISO: systemd-run --user no disponible; --cpu-max ${CPU_MAX} omitido (quedan nice, ionice y n_jobs)." >&2
  fi
fi

EXTRA=()
[ -n "$N_JOBS" ] && EXTRA+=(--n-jobs "$N_JOBS")
SINC=()
[ "$SIN_CACHE" -eq 1 ] && SINC+=(--sin-cache)

# (4) Señales: terminar la etapa en curso (y con ella los workers de loky) y marcar la corrida como interrumpida.
INTERRUMPIDO=0; ERROR=0; FALLO_COMPUERTA=0; PID=""
limpiar() {
  INTERRUMPIDO=1
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID" 2>/dev/null
    for h in $(pgrep -P "$PID" 2>/dev/null); do kill -TERM "$h" 2>/dev/null; done
    # una llamada nativa larga (BLAS/LAPACK) ignora SIGTERM: escalar a SIGKILL tras 10 s
    for _ in $(seq 1 20); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "$PID" 2>/dev/null; then
      for h in $(pgrep -P "$PID" 2>/dev/null); do kill -KILL "$h" 2>/dev/null; done
      kill -KILL "$PID" 2>/dev/null
    fi
    wait "$PID" 2>/dev/null
  fi
  echo "[f02] INTERRUMPIDO: workers terminados; NO se commitea." >&2
  exit 130
}
trap limpiar INT TERM

# Una etapa = `python -m pitcheo.recursos --etapa NOMBRE -- <comando>`: mide tiempo, RAM pico (con hijos) y CPU %.
run_etapa() {
  local nombre="$1"; shift
  echo "=== [f02] etapa: $nombre ==="
  ${PRE[@]+"${PRE[@]}"} uv run python -m pitcheo.recursos --etapa "$nombre" -- "$@" &
  PID=$!
  wait "$PID"; local rc=$?
  PID=""
  case "$rc" in
    0) ;;
    2) FALLO_COMPUERTA=1 ;;
    130|143|137) INTERRUMPIDO=1 ;;
    *) ERROR=1 ;;
  esac
  return "$rc"
}

st_pruebas()   { run_etapa pruebas uv run pytest -q; }
st_escala()    { run_etapa escala uv run pitcheo f02 --etapa escala --escala 635000 "$@" ${EXTRA[@]+"${EXTRA[@]}"}; }
st_sintetica() { run_etapa sintetica uv run pitcheo f02 --etapa sintetica ${SINC[@]+"${SINC[@]}"} ${EXTRA[@]+"${EXTRA[@]}"}; }
st_real()      { run_etapa real uv run pitcheo f02 --etapa real ${EXTRA[@]+"${EXTRA[@]}"}; }

case "$ETAPA" in
  pruebas)   st_pruebas ;;
  escala)    st_escala ;;
  sintetica) st_sintetica ;;
  real)      st_real ;;
  todo)
    st_pruebas || { echo "[f02] las pruebas fallaron: no se toca nada más." >&2; exit 1; }
    st_escala --reusar
    [ "$INTERRUMPIDO" -eq 0 ] && [ "$ERROR" -eq 0 ] && st_sintetica
    [ "$INTERRUMPIDO" -eq 0 ] && [ "$ERROR" -eq 0 ] && st_real
    ;;
esac

echo
echo "Recursos por etapa: reports/f02_recursos.json"
if [ "$INTERRUMPIDO" -eq 1 ]; then echo "[f02] corrida interrumpida: no se commitea." >&2; exit 130; fi
if [ "$ERROR" -eq 1 ]; then echo "[f02] una etapa falló con error: no se commitea." >&2; exit 1; fi
if [ "$COMMIT" -eq 1 ]; then
  git add reports/ docs/figuras/ && git commit -m "fase-02: resultados locales (etapa $ETAPA)" && echo "[f02] commit hecho; falta: git push"
else
  echo "Para commitear: git add reports/ docs/figuras/ && git commit -m \"fase-02: resultados locales\" && git push   (o repite con --commit)"
fi
[ "$FALLO_COMPUERTA" -eq 1 ] && { echo "[f02] alguna compuerta falló o la fase quedó detenida: ver el Bloque para el orquestador." >&2; exit 2; }
echo "F2 lista. Revisa reports/FASE_02.md y reports/FASE_02_sintetica.md."
exit 0
