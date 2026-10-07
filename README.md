# pitcheo — Stuff+ LMB calibrado por densidad del aire

Reto Diablos Rojos (Hackathon ISAC 2026). Estima la calidad de pitcheo (Stuff+)
corrigiendo por la densidad del aire de cada parque, con datos Trackman de la LMB.

**Lee primero `ROADMAP.md`** (plan maestro) y `CLAUDE.md` (reglas). El código y los
resultados agregados viven en GitHub; **los datos nunca** (están bajo NDA, solo en
la laptop de Rodrigo, en `data/raw/`, fuera de git).

## Dos lugares

- **Claude Code (chat)**: escribe código y lo prueba contra el generador **sintético**
  `src/pitcheo/sintetico.py`. No ve los datos reales.
- **Laptop de Rodrigo**: baja la rama de la fase, corre el script sobre `data/raw/` y
  sube solo reportes, `.json` de cifras y figuras agregadas.

## Cómo correr

El entorno vive fuera de la carpeta del repo (ROADMAP §0.3):

```bash
export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/calidad-de-pitcheo
uv python pin 3.12      # LightGBM necesita Python 3.12
uv sync --extra dev     # primera vez
uv run pytest -q        # debe pasar antes de entregar (datos sintéticos)
```

### Fase F0.0 — inspección de los tres formatos crudos

En local, con `data/raw/stuff_model_df.{parquet,pkl,rds}`:

```bash
bash scripts/fases/f00_0.sh
# escribe reports/FASE_00_0.md (Bloque para el orquestador), reports/fase_00_0.json
# y reports/logs/f00_0_<fecha>.log; sale con código != 0 si una compuerta falla.
```

Sin datos reales (p. ej. en Claude Code), se puede ejercitar el mismo camino con
datos sintéticos:

```bash
uv run pitcheo f00_0 --sintetico 40
```

### Fase F0 — ingesta, limpieza y QA por identidades

En local, con `data/raw/stuff_model_df.parquet` (fuente canónica):

```bash
bash scripts/fases/f00.sh
# escribe data/interim/pitches.parquet (particionado por year, fuera de git),
# reports/FASE_00.md (Bloque para el orquestador), reports/fase_00.json,
# docs/figuras/f00/ y reports/logs/f00_<fecha>.log; sale con código != 0 si falla
# una compuerta (G0.1-G0.9), después de escribir el reporte.
```

Implementa los ADR-002 a 007 (ROADMAP §1.1), los ADR-010 a 013 (§1.2: banderas desde `pitch_call_h`, medias
entradas A/B, `excluir_cadena`), la enmienda de ADR-010 y los ADR-014 (§1.3: los polinomios son los 9P permutados, con
`t_s` por lanzamiento; marco temporal único, `t_p`, plano y signo de `PlateLocSide`) y, desde v2.6 (§1.4), el ADR-016:
`OutsOnPlay` no es un registro fiel de los outs, y el «out faltante» de una media entrada se separa en **U** (out no
contabilizado, p. ej. una doble matanza registrada como 1 out) y **L** (turno perdido) con la Prop. 16. Texto completo en
`docs/DECISIONES.md`. Usa las categorías reales de `config/categorias.yaml` (`docs/diccionario.csv` es del organizador y no
se edita). Un valor sin regla nunca se asigna en silencio: va a la tabla "sin regla" del reporte, no se escribe
`pitches.parquet` y la fase falla (G0.5). Revisa en el reporte la tabla `play_result × pitch_call_h × KorBB` con el evento
terminal asignado.

El reporte dice qué `y_p` y signo de `PlateLocSide` eligieron los datos (ADR-014) y si la config vigente
(`fisica.y_plato_ft`, `fisica.signo_plateloc_x`) coincide, y trae, para ADR-016, el conjunto T, la Prop. 16 (`r̂_b`, `θ̂_b` con
IC95 por bootstrap de juegos), la Prop. 17 (`W(Γ)`, `SE_ref`) y las corroboraciones (a)–(e). **G0.9** clasifica el mecanismo
(U / L / mezcla; se reporta siempre) y **G0.8′ decide si se puede pasar a F1** (`W(Γ=2) ≤ 3.92·SE_ref`). Las reglas y umbrales
están fijados en `config/default.yaml`. `uv run pitcheo f00 --aplicar` reescribe en ese archivo lo que midió F0: `y_p` y el
signo, `qa.mecanismo_outs` y `qa.perdida_ignorable` (los leen F4, F6 y F8).

Sin datos reales: `uv run pitcheo f00 --sintetico 40 --out /tmp/f0` (todo, incluidos los reportes,
va a `--out`; con `--sintetico` los comandos **nunca** escriben en `reports/`, donde viven los
reportes reales).

### Fase F2 — densidad del aire por juego desde la trayectoria

En local, con `data/interim/pitches.parquet` (salida de F0):

```bash
bash scripts/fases/f02.sh
# corre pytest, `pitcheo f02` (análisis + estudio de simulación) y la prueba de escala; escribe
# data/interim/densidad_juego.parquet (por juego, fuera de git), reports/FASE_02.md (Bloque para el orquestador),
# reports/fase_02.json, reports/f02_escala.json, docs/figuras/f2/ y reports/logs/f02_<fecha>.log;
# sale con código != 0 si una compuerta (G2.1, G2.2, G2.3a, G2.3b, G2.4) falla, después de escribir el reporte.
```

Implementa las Props. 1, 2′ y 3″ de `docs/MODELO_MATEMATICO.md` §F2 y el ADR-017 (`docs/DECISIONES.md`):

- **Solver.** LSMR disperso (Fong y Saunders 2011) sobre la matriz de diseño completa; equivale a las proyecciones alternadas
  a ≤ 1e-8 en δ̂ y residuos (prueba de regresión en 5 000 lanzamientos, `tests/test_fisica_sintetica.py`). Config
  `f02.solver: lsmr | alternando`.
- **G2.1 es un estudio de simulación** pre-registrado: R = 10 réplicas (semillas 101–110, 150 juegos × ≈250 lanzamientos)
  en paralelo con `joblib`, por nivel |sesgo relativo medio| + 1.96·MCSE < 1 %; reporta además SE empírico, RMSE y cobertura
  del IC95 CR2. **No se ajustan umbrales, semillas ni tamaños a la vista del resultado**; si una compuerta falla, la fase se
  detiene y se documenta en `docs/discrepancias/`.
- **G2.3a / G2.3b.** G2.3a = Deming (pendiente ∈ [0.85, 1.15]). G2.3b = ĉ por parque con el detector ê (id de parque si se
  declara `f02.columna_parque`; si no, parque latente por mezcla gaussiana 🔎), centrado en la mediana de su cubeta, Wald con
  SE CR2 y Benjamini–Hochberg al 5 %; su potencia (≥ 0.80 para |c| = 0.02) y su tasa de falsos positivos (≤ 0.05) se miden en
  una sintética con λ = 1.02 y τ = 1.01 inyectados en subconjuntos de 18 parques. Si `SpinAxis` resulta circular (inferido del
  movimiento), G2.3b se declara **no evaluable**.
- **Escala.** `uv run pitcheo f02 --escala 635000` genera ≈ 635 k lanzamientos sintéticos, corre el análisis completo y
  reporta tiempo y RAM pico (`reports/f02_escala.json`).

Sin datos reales: `uv run pitcheo f02 --sintetico 150 --out /tmp/f2` (todo va a `--out`).

La CLI tiene un subcomando por fase (`pitcheo f00_0`, `f00`, `f01` … `f11`); las
fases F3 en adelante están pendientes.

## Confidencialidad

Nunca se versiona `data/`, `artefactos/`, `reports/privado/`, `*.parquet`, `*.pkl`,
`*.rds` ni credenciales (ver `.gitignore` y `CLAUDE.md`). Los logs y reportes solo
contienen formas y agregados, nunca filas por lanzamiento.
