# CLAUDE.md — reglas del proyecto `calidad-de-pitcheo`

Claude Code (en chat, conectado a este repo) lee este archivo al iniciar cada sesión.
El plan completo está en `ROADMAP.md`. El flujo es el mismo de `Historia-de-un-entrenador`:
el código y los resultados agregados viven en GitHub; los datos, nunca.

## Contexto
- Reto Stuff+ de Diablos Rojos (Hackathon ISAC 2026). Datos Trackman de la LMB, 3 temporadas, bajo NDA.
- Diccionario de columnas: `docs/diccionario.csv`. Las columnas `target_only` nunca son features.
  Los `*_anon_id` solo sirven para agrupar, validar y agregar.
- `docs/diccionario.csv` es del organizador y **no se edita**. Las categorías reales y sus
  mapas viven en `config/categorias.yaml` (ADR-002 a 007, ROADMAP §1.1). Un valor sin regla
  nunca se asigna en silencio: hace fallar la fase.
- Idioma de código, comentarios, reportes y commits: español.

## No tienes los datos
- Los datos reales están solo en la laptop de Rodrigo, en `data/raw/`
  (`stuff_model_df.parquet`, `.pkl`, `.rds`: el mismo dataset en tres formatos). Fuera de git.
- Todo se desarrolla y prueba aquí contra el generador sintético `src/pitcheo/sintetico.py`,
  que respeta el esquema del diccionario. `uv run pytest -q` debe pasar antes de entregar.
- Lo que deba correr sobre datos reales va en `pitcheo fXX` y `scripts/fases/fXX.sh`.
  Rodrigo lo corre en local y sube el reporte.
- Para saber cómo son los datos reales, lee `reports/FASE_00_0.md` y los reportes posteriores.
  No pidas filas.

## Entrega de cada fase
1. Leer la sección de la fase en `ROADMAP.md` y el sufijo §0.3.
2. Si la fase empieza con Opus: primero la matemática en `docs/MODELO_MATEMATICO.md`, luego el código.
3. Rama `faseXX`, PR a `main`.
4. Terminar la respuesta con el bloque de comandos locales de ROADMAP §0.2 con el número correcto.
5. Tras la corrida local: prompt de revisión §0.4. Merge y tag `faseXX` solo si todas las compuertas pasan.

## Lo que el script de cada fase garantiza
- Fuente canónica: `data/raw/stuff_model_df.parquet` (desde F0: `data/interim/pitches.parquet`).
  `data/raw/` es de solo lectura.
- `reports/FASE_XX.md` con el **Bloque para el orquestador** (ROADMAP §5), cifras con intervalo
  y etiqueta de evidencia (🟢 🟡 ⚪ 🔎), más sus `.json`.
- Figuras agregadas en `docs/figuras/fXX/`, log fechado en `reports/logs/`.
- Código de salida ≠ 0 si una compuerta falla (después de escribir el reporte).
- Entorno fuera de la carpeta: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/calidad-de-pitcheo`.
- Todo parámetro en `config/default.yaml`. Semillas fijas.

## Confidencialidad
- Nunca filas por lanzamiento en `reports/`, logs ni figuras. Los logs imprimen formas y agregados.
- Tablas por lanzador solo en `reports/privado/` (fuera de git).
- Nunca commitear `data/`, `artefactos/`, `*.parquet`, `*.pkl`, `*.rds`, `credenciales.env`.

## Cuándo detenerse
Escribir `docs/discrepancias/DXX.md`, no hacer merge y decir qué pegarle al orquestador si:
- una compuerta falla;
- un resultado contradice la física;
- se detecta una alternativa mejor que lo especificado;
- un cambio podría empeorar validez o reproducibilidad.

## Lo que Claude Code no hace
- No modifica `ROADMAP.md` ni `docs/HIPOTESIS.md` (solo el orquestador).
- No cambia la regla de una hipótesis pre-registrada después de ver resultados.
- No racionaliza un resultado inesperado: lo reporta.
- No usa ubicación (`PlateLoc*`, `in_strike_zone`, `EffectiveVelo`, VAA crudo) en Stuff+ puro.
- No elige por su cuenta entre los tres archivos crudos si no son equivalentes.
