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
# una compuerta (G0.1-G0.6), después de escribir el reporte.
```

Implementa los ADR-002 a 007 (ROADMAP §1.1) y, desde v2.4, los ADR-010 a 013 (§1.2: ejes de los polinomios,
banderas desde `pitch_call_h`, medias entradas A/B y `excluir_cadena`); texto completo en `docs/DECISIONES.md`. Usa las
categorías reales de `config/categorias.yaml` (`docs/diccionario.csv` es del organizador y no se
edita). Un valor sin regla nunca se asigna en silencio: va a la tabla "sin regla" del reporte, no se
escribe `pitches.parquet` y la fase falla (G0.5). Revisa en el reporte la tabla
`play_result × pitch_call_h × KorBB` con el evento terminal asignado.

Sin datos reales: `uv run pitcheo f00 --sintetico 40 --out /tmp/f0` (todo, incluidos los reportes,
va a `--out`; con `--sintetico` los comandos **nunca** escriben en `reports/`, donde viven los
reportes reales).

La CLI tiene un subcomando por fase (`pitcheo f00_0`, `f00`, `f01` … `f11`); las
fases posteriores a F0 están pendientes.

## Confidencialidad

Nunca se versiona `data/`, `artefactos/`, `reports/privado/`, `*.parquet`, `*.pkl`,
`*.rds` ni credenciales (ver `.gitignore` y `CLAUDE.md`). Los logs y reportes solo
contienen formas y agregados, nunca filas por lanzamiento.
