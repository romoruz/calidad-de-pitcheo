# FASE 00.0 — Inspección de los tres formatos crudos

## Tamaños en disco

- parquet: 211.24 MB
- pkl: 446.77 MB
- rds: 136.83 MB

## Equivalencia de formatos (criterio 1-4, ROADMAP §4-F0.0)

- **pkl**: equivalentes=True · PitchUID comparable=True · columnas distintas=0
- **rds**: equivalentes=True · PitchUID comparable=True · columnas distintas=0

## Perfil del parquet contra el diccionario

- filas: 635,002
- columnas no documentadas: ninguna
- columnas del diccionario ausentes: ninguna

- incumplimientos de unit_or_values: ["PitcherThrows (valores: ['Undefined'])", "BatterSide (valores: ['Switch', 'Undefined'])", "AutoPitchType (valores: ['Knuckleball', 'OneSeamFastBall', 'Sweeper', 'TwoSeamFastBall'])", "PitchCall (valores: ['FoulBallFieldable', 'FoulBallNotFieldable', 'Undefined'])", 'Outs (rango: 8 fuera)']

## Alcance del dataset

- filas: 635,002 · PitchUID únicos: 635,002
- juegos: 2127 · lanzadores: 1135 · bateadores: 865
- year: [2024, 2025, 2026]
- altitude_category: [{'altitude_category': 'No Altitude', 'n': 293875}, {'altitude_category': 'Extreme Altitude', 'n': 183267}, {'altitude_category': 'Medium Altitude', 'n': 154840}, {'altitude_category': None, 'n': 3020}]

## Bloque para el orquestador — F00.0

- Modelo(s) usado(s): Sonnet (andamiaje) / Opus (revisión)
- Compuertas: G00.1 ✅ | G00.2 ✅ | G00.3 ✅
- Cifras clave: 635,002 lanzamientos, 2127 juegos, 1135 lanzadores
- Desviaciones respecto al ROADMAP: ninguna
- Mejora posible detectada: ninguna
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase00_0 / (pendiente) / (pendiente)
- Log: reports/logs/f00_0_<fecha>.log

> Si G00.1 o G00.2 fallan, el **orquestador** elige la fuente canónica (el código NUNCA elige por su cuenta).
