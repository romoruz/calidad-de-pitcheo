# FASE 00 — Ingesta y QA por identidades

Filas de entrada: 635,002 · filas de salida: 635,002 · 3.0s

`data/interim/pitches.parquet` particionado por year: 2024: 243,254, 2025: 256,144, 2026: 135,604

## Valores sin regla (G0.5)

Ninguno: todo valor de las columnas inventariadas tiene regla en `config/categorias.yaml`.

## Tipos normalizados

- Int32 → Int64: 1 columnas (year)
- String → Float64: 1 columnas (EffectiveVelo)
- Float64 → Boolean: 17 columnas (is_swing, is_whiff, is_contact, is_called_strike, is_swinging_strike, is_ball_in_play, …)
- Float64 → Int64: 6 columnas (RunsScored, OutsOnPlay, Inning, Outs, Balls, Strikes)
- Int32 → Boolean: 1 columnas (in_strike_zone)

## Identidades (ROADMAP §4-F0)

| ID | cumplimiento | n | detalle |
|---|---|---|---|
| I1 | 100.0000 % | 635,002 | tol. 0.05 mph |
| I2 | 100.0000 % | 635,002 | exacta |
| I3 | 0.0000 % | 635,002 | X: 0.0000 %, 2c2/a0=-1.8680 · Y: 0.0000 %, 2c2/a0=-0.9992 · Z: 0.3351 %, 2c2/a0=0.1749 |
| I4 | 100.0000 % | 634,300 | pendiente (origen) 1.0000, con intercepto 1.0000, r=1.000000 |
| I5 | 100.0000 % | 634,300 | R=0.999287, espejo=False, desfase aprendido 180.0° |
| I6′ | 99.7491 % | 634,161 | suma 99.9290 % · contacto⇔Foul/InPlay 99.7491 % · whiff⇒StrikeSwinging 100.0000 % |
| I7 | 86.1167 % | 37,023 | n son medias entradas; sin la última de cada juego: 86.5887 %; distribución de outs {'0': 75, '1': 201, '2': 4763, '3': 31883, '4': 84, '5': 8, '6': 7, '8': 1, '9': 1} |
| I8 | 87.5000 % | 8 | tipos: Changeup=✓, Curveball=✓, Cutter=✗, Four-Seam=✓, Sinker=✓, Slider=✓, Splitter=✓, Sweeper=✓ |
| I9 | 100.0000 % | 2,117 | juegos incoherentes: 0 |
| I10 | 99.9987 % | 635,002 | violaciones: 8 {'3.0': 8} |

## Alcance del dataset (agregado)

- 635,002 lanzamientos · 2,127 juegos · 1,134 lanzadores · 864 bateadores · years [2024, 2025, 2026]
- lanzadores por número de cubetas: {'1': 185, '2': 200, '3': 665}
- lanzadores con ≥30 lanzamientos en ≥2 cubetas (identificación intra-lanzador): 765

### year × cubeta (cubeta imputada por juego, ADR-005)

| year | cubeta | juegos | lanzadores | lanzamientos |
|---|---|---|---|---|
| 2024 | Extreme Altitude | 223 | 464 | 66,619 |
| 2024 | Medium Altitude | 204 | 434 | 60,934 |
| 2024 | No Altitude | 406 | 483 | 115,701 |
| 2025 | (sin cubeta) | 3 | 53 | 947 |
| 2025 | Extreme Altitude | 237 | 495 | 72,720 |
| 2025 | Medium Altitude | 213 | 451 | 65,981 |
| 2025 | No Altitude | 386 | 507 | 116,496 |
| 2026 | (sin cubeta) | 7 | 53 | 2,073 |
| 2026 | Extreme Altitude | 144 | 400 | 43,928 |
| 2026 | Medium Altitude | 92 | 283 | 27,925 |
| 2026 | No Altitude | 212 | 421 | 61,678 |

## play_result × pitch_call_h × KorBB → evento terminal (ADR-007)

Revisa que ninguna combinación inesperada tenga un evento que no debería.

| play_result | pitch_call_h | KorBB | evento_terminal | n |
|---|---|---|---|---|
| BallCalled | BallCalled | Undefined | — | 210,743 |
| NeutralPlay | Foul | Undefined | — | 106,877 |
| NeutralPlay | StrikeCalled | Undefined | — | 91,484 |
| Out | InPlay | Undefined | OUT_BIP | 66,920 |
| StrikeSwinging | StrikeSwinging | Undefined | — | 47,593 |
| Single | InPlay | Undefined | 1B | 28,579 |
| Strikeout | StrikeSwinging | Strikeout | K | 24,320 |
| Walk | BallCalled | Walk | BB | 15,317 |
| BallinDirt | BallinDirt | Undefined | — | 10,864 |
| Double | InPlay | Undefined | 2B | 7,800 |
| Strikeout | StrikeCalled | Strikeout | K | 6,325 |
| HomeRun | InPlay | Undefined | HR | 4,616 |
| FieldersChoice | InPlay | Undefined | OUT_BIP | 3,640 |
| HitByPitch | HitByPitch | Undefined | HBP | 2,258 |
| Sacrifice | InPlay | Undefined | SAC | 1,932 |
| FoulBallFieldable | Foul | Undefined | — | 1,917 |
| Error | InPlay | Undefined | ROE | 1,747 |
| NeutralPlay | Undefined | Undefined | — | 841 |
| Triple | InPlay | Undefined | 3B | 705 |
| Walk | BallinDirt | Walk | BB | 489 |
| Walk | HitByPitch | Walk | BB | 22 |
| NeutralPlay | InPlay | Undefined | — | 7 |
| Strikeout | Foul | Strikeout | K | 3 |
| Out | BallCalled | Undefined | — | 1 |
| Out | StrikeSwinging | Undefined | — | 1 |
| Walk | StrikeCalled | Walk | BB | 1 |

### Incoherencias (se reportan, no fallan)

| regla | n | pct |
|---|---|---|
| resultado de bola en juego sin pitch_call_h=InPlay | 2 | 0.0003 |
| pitch_call_h=InPlay con play_result sin regla de bola en juego (-> no terminal) | 7 | 0.0011 |
| play_result=Strikeout con KorBB distinto de Strikeout | 0 | 0.0 |
| play_result=Walk con KorBB distinto de Walk | 0 | 0.0 |
| play_result=HitByPitch con pitch_call_h distinto de HitByPitch | 0 | 0.0 |
| KorBB terminal con pitch_call_h=Undefined | 0 | 0.0 |

## Imputaciones y exclusiones por ADR

- **ADR-002 familia:** {'FF': 217618, 'SL': 139717, 'SI': 110899, 'CH': 86214, 'CU': 54024, 'FC': 26468, 'EXC': 62} · Sweeper (`es_sweeper`): 588 · EXC: 62
- **ADR-003 lanzador:** mano indefinida 1,421 (0.2238 %) → moda 0 · signo de RelSide 1,421 · descartadas 0 (0.0 %). Signo aprendido: derecha ⇔ RelSide > 0, concordancia 99.1548% sobre 633,581 filas (umbral 99%, regla activa)
- **ADR-003 bateador:** Switch 54 (resueltos con la mano opuesta: 54) · Undefined/nulo 1,216 (0.1915 %) → imputados 53 · descartados 1,163 (0.1831 %)
- **ADR-004:** 108,797 fouls unificados · `Undefined` excluido: 841 (0.1324 %)
- **ADR-005 cubeta:** nulas crudas 3,020 (0.4756 %) → imputadas por juego 0 · quedan sin cubeta 3,020 filas (0.4756 %) en 10 juegos enteros nulos (F2 les predice la cubeta, 🔎) · juegos con >1 cubeta: 0
- **ADR-006 Outs:** inválidos 8 (0.0013 %) · nulos 0
- **ADR-007 eventos:** {'NO_TERMINAL': 470328, 'OUT_BIP': 70560, 'K': 30648, '1B': 28579, 'BB': 15829, '2B': 7800, 'HR': 4616, 'HBP': 2258, 'SAC': 1932, 'ROE': 1747, '3B': 705}
- IDs nulos (informativo, no hay ADR): {'pitcher_anon_id': 3272, 'batter_anon_id': 2020, 'catcher_anon_id': 2325, 'game_anon_id': 0}

### Exclusiones de modelos y cadena (`excluir_modelo`)

| motivo | n | pct |
|---|---|---|
| ADR-002:EXC | 62 | 0.0098 |
| ADR-003:lanzador | 0 | 0.0 |
| ADR-003:bateador | 1,163 | 0.1831 |
| ADR-004:Undefined | 841 | 0.1324 |
| ADR-006:Outs | 8 | 0.0013 |

Total (unión, sin doble conteo): **2,074** lanzamientos = **0.3266 %**.

## Compuertas

- **G0.1** ❌ I1 100.0000 % · I2 100.0000 % · I6′ 99.7491 % (mín. 99.9%)
- **G0.2** ❌ I3 0.0000 % (mín. 99%); razón 2·c2/a0 por eje: X=-1.8680, Y=-0.9992, Z=0.1749 — si falla: documentar la convención, no forzarla
- **G0.3** ❌ I7 86.1167 % de 37,023 medias entradas (mín. 90%)
- **G0.4** ✅ I9 100.0000 % de 2,117 juegos con cubeta
- **G0.5** ✅ valores sin regla: 0
- **G0.6** ✅ exclusiones 0.327 % de los lanzamientos (máx. 3%)

### Bloque para el orquestador — F00
- Modelo(s) usado(s): Sonnet
- Compuertas: G0.1 ❌ | G0.2 ❌ | G0.3 ❌ | G0.4 ✅ | G0.5 ✅ | G0.6 ✅
- Cifras clave: 635,002 lanzamientos · 2,127 juegos · exclusiones 0.3266 % · I1 100.0000 % · I3 0.0000 % · I7 86.1167 %
- Desviaciones respecto al ROADMAP: ninguna
- Mejora posible detectada: ninguna
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase00 / (pendiente) / (pendiente)
- Log: reports/logs/f00_<fecha>.log
