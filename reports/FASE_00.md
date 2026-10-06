# FASE 00 — Ingesta y QA por identidades

Filas de entrada: 635,002 · filas de salida: 635,002 · 6.6s

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
| I7 | 86.1167 % | 37,023 | criterio A estricto (n = medias entradas); A sin la final: 86.5887 %; **B (no finales): 91.9790 %**; inconsistentes (≥4 outs): 101; outs por media entrada {'0': 75, '1': 201, '2': 4763, '3': 31883, '4': 84, '5': 8, '6': 7, '8': 1, '9': 1} |
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
| Out | StrikeSwinging | Undefined | — | 1 |
| Out | BallCalled | Undefined | — | 1 |
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

- **ADR-011 desenlace desde pitch_call_h:** {'es_swing': 296657, 'es_whiff': 71914, 'es_contacto': 224743, 'es_foul': 108797, 'es_bip': 115946}
- **ADR-012 medias entradas:** {'medias_entradas': 37023, 'finales': 2127, 'no_finales': 34896, 'A': 31883, 'pct_A': 86.1167, 'B_no_finales': 32097, 'pct_B_no_finales': 91.979, 'inconsistentes': 101, 'distribucion_outs': {'0': 75, '1': 201, '2': 4763, '3': 31883, '4': 84, '5': 8, '6': 7, '8': 1, '9': 1}}

### excluir_modelo (ADR-002/003/004/006 + ID de lanzador nulo, ADR-013)

| motivo | n | pct |
|---|---|---|
| ADR-002:EXC | 62 | 0.0098 |
| ADR-003:lanzador | 0 | 0.0 |
| ADR-003:bateador | 1,163 | 0.1831 |
| ADR-004:Undefined | 841 | 0.1324 |
| ADR-006:Outs | 8 | 0.0013 |
| ADR-013:pitcher_id_nulo | 3,272 | 0.5153 |

Total (unión, sin doble conteo): **5,102** lanzamientos = **0.8035 %**.

### excluir_cadena (ADR-013: solo lo que invalida la transición del conteo)

| motivo | n | pct |
|---|---|---|
| ADR-004:Undefined | 841 | 0.1324 |
| ADR-006:Outs | 8 | 0.0013 |
| ADR-013:InPlay_sin_resultado | 7 | 0.0011 |

Total (unión, sin doble conteo): **856** lanzamientos = **0.1348 %**.

## ADR-010 (enmienda v2.5) — los polinomios de trayectoria son los 9P en otros ejes

n = 635,002 filas. Cada celda es **R² (pendiente)** de la regresión simple de la fila (eje del polinomio) sobre la columna (eje de los 9P).

**c2 del polinomio sobre aceleración a0 (ax0, ay0, az0)**

| polinomio \ 9P | x | y | z |
|---|---|---|---|
| X | 0.0826 (-0.059) | 1.0000 (+0.500) | 0.3803 (+0.156) |
| Y | 0.0711 (-0.108) | 0.3803 (+0.609) | 1.0000 (+0.500) |
| Z | 1.0000 (+0.500) | 0.0826 (-0.349) | 0.0711 (-0.164) |

**c1 del polinomio sobre velocidad v0 (vx0, vy0, vz0)**

| polinomio \ 9P | x | y | z |
|---|---|---|---|
| X | 0.0345 (-0.278) | 0.9997 (+1.001) | 0.1968 (+1.260) |
| Y | 0.0084 (-0.052) | 0.2638 (+0.195) | 0.9889 (+1.070) |
| Z | 0.9980 (+1.037) | 0.0390 (-0.137) | 0.0078 (-0.173) |

**c0 del polinomio sobre posición r0 (x0, y0, z0)**

| polinomio \ 9P | x | y | z |
|---|---|---|---|
| X | 0.0045 (+0.024) | 0.0000 (-2764.182) | 0.0006 (+0.029) |
| Y | 0.0133 (+0.036) | 0.0000 (+179.864) | 0.9554 (+1.059) |
| Z | 0.9970 (+1.111) | 0.0000 (+3691.023) | 0.0145 (+0.465) |

- Permutación (elegida con **c2**, que no depende del origen de tiempo): {'X': 'y', 'Y': 'z', 'Z': 'x'} · signos {'X': 1, 'Y': 1, 'Z': 1} · escala |2·pendiente(c2)| {'X': '1.0000', 'Y': '1.0000', 'Z': '1.0000'}
- c2: R² por pares mín. **1.000000** · regresión conjunta mín. **1.000000** (exigido 0.9999)
- **t_s por lanzamiento** = (s·c1_X − v0)/a0 (n = 635,002): mediana -0.03630 s · IQR 0.00750 s · p1 -0.05131 · p99 -0.02476  (negativo = el polinomio arranca ANTES de y = 50 ft: en la liberación)
- t_s por eje (mediana, consistencia): X: -0.03630, Y: -0.03630, Z: -0.03608

**c1 del polinomio sobre (v0 + a0·t_s) del eje permutado** — contra v2.4, que comparaba c1 con v0 a secas:

| eje del polinomio | R² con t_s | pendiente | R² sin t_s (v2.4) | nota |
|---|---|---|---|---|
| X | 1.000000 | 1.00000 | 0.9997 | eje de referencia: 1 por construcción |
| Y | 1.000000 | 1.00000 | 0.9889 | prueba independiente |
| Z | 1.000000 | 1.00000 | 0.9980 | prueba independiente |

- R² mín. de c1 con t_s: **1.000000** (exigido 0.999)
- **Decisión: `equivalentes`** — los polinomios son los 9P en ejes permutados con el origen de tiempo en la liberación; sirven de verificación cruzada.

Regresión conjunta de c2 (informativa): cada eje del polinomio sobre los tres ejes de los 9P a la vez.

| eje del polinomio | R² | coef. sobre (x, y, z) | intercepto |
|---|---|---|---|
| X | 1.000000 | (+0.0000, +0.5000, -0.0000) | -0.0000 |
| Y | 1.000000 | (-0.0000, +0.0000, +0.5000) | -0.0000 |
| Z | 1.000000 | (+0.5000, +0.0000, -0.0000) | -0.0000 |

## ADR-014 — marco temporal único de los 9P

El reloj de los 9P arranca en y0 = 50 ft; `ZoneTime` y los polinomios arrancan en la liberación. El tiempo al plato t_p es la raíz de y(t_p) = y_p con los 9P (no `ZoneTime`). Se elige el plano y_p y el signo s de `PlateLocSide = s·x(t_p)` por mínimo error mediano. |error| en pies, mediana / p99:

n = 635,002

| y_p (ft) | signo s | PlateLocSide | PlateLocHeight | elegida |
|---|---|---|---|---|
| 1.4167 | +1 | 1.2236 / 4.8221 | 0.0013 / 0.0318 |  |
| 1.4167 | -1 | 0.0017 / 0.0091 | 0.0013 / 0.0318 | ✅ |
| 0.0000 | +1 | 1.2448 / 4.9043 | 0.1551 / 0.3307 |  |
| 0.0000 | -1 | 0.0359 / 0.1444 | 0.1551 / 0.3307 |  |

- **Verificación de ZoneTime** con t_s por lanzamiento: |ZoneTime − (t_p − t_s)| mediana **0.00003 s** · p99 0.00011 s (n = 635,002). Lo que se hacía mal, |ZoneTime − t_p|: mediana 0.03626 s.
- Config vigente (`fisica.y_plato_ft`, `fisica.signo_plateloc_x`): y_p = 1.4166667, s = -1. Coincide con la elegida por los datos.

## ADR-011 — banderas is_* del organizador vs. pitch_call_h

El árbol de desenlaces se define desde `pitch_call_h` (partición exacta); las `is_*` son verificación cruzada. Abajo, solo las combinaciones que **discrepan**; la tabla completa (cada combinación con su n) está en `reports/fase_00.json`.

| derivada | bandera | n | discrepantes | % |
|---|---|---|---|---|
| es_swing | is_swing | 634,161 | 1,141 | 0.1799 |
| es_whiff | is_whiff | 634,161 | 0 | 0.0 |
| es_contacto | is_contact | 634,161 | 1,591 | 0.2509 |
| es_bip | is_ball_in_play | 634,161 | 2 | 0.0003 |
| es_hbp | is_hit_by_pitch | 634,161 | 2,280 | 0.3595 |

| derivada | derivada_valor | bandera | bandera_valor | pitch_call_h | n |
|---|---|---|---|---|---|
| es_hbp | 1 | is_hit_by_pitch | 0 | HitByPitch | 2,280 |
| es_swing | 0 | is_swing | 1 | BallCalled | 463 |
| es_contacto | 0 | is_contact | 1 | BallCalled | 463 |
| es_contacto | 0 | is_contact | 1 | StrikeSwinging | 450 |
| es_swing | 0 | is_swing | 1 | StrikeCalled | 403 |
| es_contacto | 0 | is_contact | 1 | StrikeCalled | 403 |
| es_swing | 0 | is_swing | 1 | HitByPitch | 230 |
| es_contacto | 0 | is_contact | 1 | HitByPitch | 230 |
| es_swing | 0 | is_swing | 1 | BallinDirt | 45 |
| es_contacto | 0 | is_contact | 1 | BallinDirt | 45 |
| es_bip | 0 | is_ball_in_play | 1 | StrikeSwinging | 1 |
| es_bip | 0 | is_ball_in_play | 1 | BallCalled | 1 |

## ADR-012 / ADR-015 — medias entradas de 2 outs: ¿robo o turno final perdido?

Sin orden de lanzamientos, un turno es **incompleto** si hay lanzamientos de un bateador de la media entrada sin ningún evento terminal (lo que dejaría un robo o un pickoff con 2 outs). Si todos sus turnos terminan, la media entrada perdió su **último turno completo**.

**Clasificación de las 4,449 medias entradas NO finales de 2 outs:** turno incompleto 415 (**9.328 %**) · turno final perdido 4,034 (**90.672 %**).

| métrica | 2 outs | 3 outs |
|---|---|---|
| medias entradas | 4,763 | 31,883 |
| % que es la última del juego | 6.592 | 5.228 |
| lanzamientos por media entrada (mediana / media) | 14 / 15.1 | 16 / 17.5 |
| % con ≥1 turno incompleto | 9.469 | 2.948 |
| **ponches por out registrado** | 0.187 | 0.300 |
| eventos K por media entrada | 0.374 | 0.899 |
| eventos OUT_BIP por media entrada | 1.579 | 1.967 |
| eventos SAC por media entrada | 0.029 | 0.055 |
| eventos BB por media entrada | 0.542 | 0.41 |
| eventos HBP por media entrada | 0.081 | 0.057 |
| eventos ROE por media entrada | 0.057 | 0.046 |
| outs implicados por eventos − OutsOnPlay | {'-2': 3, '-1': 129, '0': 4585, '1': 46} | {'-3': 5, '-2': 116, '-1': 2467, '0': 29118, '1': 173, '2': 3, '3': 1} |

### Tasa de turno final perdido por cubeta (G0.8)

Sobre las medias entradas **no finales**; IC de Wilson al 95 %. Si difiere entre cubetas, la pérdida de datos se confunde con la altitud en cualquier comparación de outcomes (F8).

| cubeta | medias_entradas | dos_outs | turno_incompleto | turno_final_perdido | tasa_perdido_% | ic95_wilson_% |
|---|---|---|---|---|---|---|
| (sin cubeta) | 153 | 22 | 1 | 21 | 13.725 | [9.156, 20.072] |
| Extreme Altitude | 9,799 | 1,476 | 78 | 1,398 | 14.267 | [13.588, 14.973] |
| Medium Altitude | 8,332 | 1,091 | 115 | 976 | 11.714 | [11.041, 12.422] |
| No Altitude | 16,612 | 1,860 | 221 | 1,639 | 9.866 | [9.422, 10.329] |

**Rango entre cubetas (máx − mín): 4.400 pp** · M (turnos finales perdidos, no finales) = 4,034 de 34,896 medias entradas

**Por cubeta y año:**

| cubeta | year | medias_entradas | turno_final_perdido | tasa_perdido_% | ic95_wilson_% |
|---|---|---|---|---|---|
| (sin cubeta) | 2025 | 53 | 6 | 11.321 | [5.293, 22.577] |
| (sin cubeta) | 2026 | 100 | 15 | 15.000 | [9.306, 23.284] |
| Extreme Altitude | 2024 | 3,642 | 523 | 14.360 | [13.259, 15.537] |
| Extreme Altitude | 2025 | 3,836 | 554 | 14.442 | [13.365, 15.590] |
| Extreme Altitude | 2026 | 2,321 | 321 | 13.830 | [12.485, 15.295] |
| Medium Altitude | 2024 | 3,334 | 411 | 12.328 | [11.255, 13.487] |
| Medium Altitude | 2025 | 3,503 | 402 | 11.476 | [10.462, 12.574] |
| Medium Altitude | 2026 | 1,495 | 163 | 10.903 | [9.422, 12.584] |
| No Altitude | 2024 | 6,619 | 655 | 9.896 | [9.199, 10.639] |
| No Altitude | 2025 | 6,426 | 677 | 10.535 | [9.808, 11.310] |
| No Altitude | 2026 | 3,567 | 307 | 8.607 | [7.730, 9.572] |

### Déficits de eventos y π̂_K (ROADMAP §1.3)

Déficit = media por media entrada de las de 3 outs − media de las de 2 outs; π̂_K = d_K / (d_K + d_OUT_BIP + d_SAC). IC95 por bootstrap de medias entradas. **No se implementan los pesos ω (eso es F4).**

- **todas las de 2 outs (misma población que §1.3)** (n = 4,763 vs 31,883): d_K = 0.525 [0.506, 0.542] · d_OUT_BIP = 0.387 [0.370, 0.407] · d_SAC = 0.026 [0.021, 0.032] · **π̂_K = 0.559** [0.539, 0.577]
- **solo las de turno final perdido** (n = 4,312 vs 31,883): d_K = 0.538 [0.522, 0.557] · d_OUT_BIP = 0.363 [0.345, 0.380] · d_SAC = 0.028 [0.022, 0.033] · **π̂_K = 0.579** [0.562, 0.599]

- Agrupamiento por juego de los turnos finales perdidos: 2,126 juegos · tasa media 11.56 % · dispersión de Pearson φ = 1.10 (≈ 1 si se reparten al azar entre juegos; ≫ 1 si se concentran en algunos) · 84.7 % de los juegos con ≥ 1 · 29.9 % con > 2

> Nota de identificación: los déficits comparan las medias entradas de 2 outs con las de 3 outs **registradas**. π̂_K es una estimación gruesa: con datos sintéticos sembrados con una verdad de π_K = 0.40, 0.71 y 0.93 devuelve ≈ 0.34, 0.30 y 0.30; es decir, mide los ponches entre los terceros outs **registrados** (≈ la fracción de ponches entre todos los outs) y es **insensible** a la pérdida selectiva. Si el valor real supera claramente esa fracción, no lo explica «se pierde el último turno»: compara los **ponches por out registrado** de la tabla (iguales si solo faltara el último turno) y la dispersión por juego. Las cotas con π ∈ {0, 1} de Prop. 15 no dependen de este valor. Ver `docs/discrepancias/D01.md`.

**OutsOnPlay × evento_terminal** (¿cuenta el out de los ponches?)

| evento | OutsOnPlay | n |
|---|---|---|
| 1B | 0 | 27,675 |
| 1B | 1 | 890 |
| 1B | 2 | 13 |
| 1B | 3 | 1 |
| 2B | 0 | 7,645 |
| 2B | 1 | 151 |
| 2B | 2 | 4 |
| 3B | 0 | 699 |
| 3B | 1 | 6 |
| BB | 0 | 15,793 |
| BB | 1 | 29 |
| BB | 2 | 3 |
| BB | 3 | 4 |
| HBP | 0 | 2,256 |
| HBP | 1 | 2 |
| HR | 0 | 4,608 |
| HR | 1 | 6 |
| HR | 2 | 1 |
| HR | 3 | 1 |
| K | 1 | 30,648 |
| NO_TERMINAL | 0 | 468,839 |
| NO_TERMINAL | 1 | 1,467 |
| NO_TERMINAL | 2 | 17 |
| NO_TERMINAL | 3 | 5 |
| OUT_BIP | 0 | 162 |
| OUT_BIP | 1 | 70,179 |
| OUT_BIP | 2 | 217 |
| OUT_BIP | 3 | 2 |
| ROE | 0 | 1,697 |
| ROE | 1 | 49 |
| ROE | 2 | 1 |
| SAC | 0 | 107 |
| SAC | 1 | 1,817 |
| SAC | 2 | 8 |

## Compuertas

- **G0.1** ✅ I1 100.0000 % · I2 100.0000 % (mín. 99.9%) · I6′ 99.7491 % (mín. 99.5%) · tabla de discrepancias is_* × pitch_call_h: producida
- **G0.2** ✅ ADR-010 enmendado: permutación {'X': 'y', 'Y': 'z', 'Z': 'x'} · c2 R² por pares 1.000000 y conjunta 1.000000 (mín. 0.9999) · c1 con t_s R² mín. 1.000000 (mín. 0.999) → **equivalentes**; la trayectoria canónica sigue siendo la de los 9P
- **G0.3** ✅ diagnóstico de las 4,763 medias entradas de 2 outs producido y clasificado (no finales: 4,449): turno incompleto 9.328 % vs turno final perdido 90.672 %
- **G0.4** ✅ I9 100.0000 % de 2,117 juegos con cubeta
- **G0.5** ✅ valores sin regla: 0
- **G0.6** ✅ excluir_modelo 0.803 % (máx. 3%) · excluir_cadena 0.135 % (máx. 0.5%)
- **G0.7** ✅ ADR-014 con y_p = 1.4167 ft y signo -1: |error| mediana/p99 PlateLocSide 0.0017/0.0091 ft · PlateLocHeight 0.0013/0.0318 ft (máx. 0.05/0.3) · |ZoneTime − (t_p − t_s)| mediana 0.00003 s (máx. 0.005) · config vigente coincide
- **G0.8** ❌ tasa de turno final perdido por cubeta (todos los años): Extreme Altitude 14.27 %, Medium Altitude 11.71 %, No Altitude 9.87 % · máx − mín = 4.400 pp (máx. 3.0 pp) → **DISCREPANCIA: la pérdida de datos se confunde con la altitud; no se sigue a F1**

### Bloque para el orquestador — F00
- Modelo(s) usado(s): Sonnet
- Compuertas: G0.1 ✅ | G0.2 ✅ | G0.3 ✅ | G0.4 ✅ | G0.5 ✅ | G0.6 ✅ | G0.7 ✅ | G0.8 ❌
- Cifras clave: 635,002 lanzamientos · 2,127 juegos · excluir_modelo 0.8035 % · excluir_cadena 0.1348 % · I1 100.0000 % · I6′ 99.7491 % · I7 A 86.1167 % / B no finales 91.9790 % · ADR-010: equivalentes · t_s mediana -0.0363 s · ADR-014 y_p 1.4167 ft, signo -1, |ZoneTime−(t_p−t_s)| mediana 0.00003 s · turno final perdido: rango entre cubetas 4.400 pp · π̂_K 0.559
- Desviaciones respecto al ROADMAP: ninguna (compuertas v2.5: ADR-010 enmendado, 014 y 015)
- Mejora posible detectada: ninguna
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase00 / (pendiente) / (pendiente)
- Log: reports/logs/f00_<fecha>.log
