# FASE 00 — Ingesta y QA por identidades

Filas de entrada: 635,002 · filas de salida: 635,002 · 8.0s

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
| I3 | 0.0000 % | 635,002 | **sustituida por G0.2 (ADR-010)**, ya no es compuerta; X: 0.0000 %, 2c2/a0=-1.8680 · Y: 0.0000 %, 2c2/a0=-0.9992 · Z: 0.3351 %, 2c2/a0=0.1749 |
| I4 | 100.0000 % | 634,300 | pendiente (origen) 1.0000, con intercepto 1.0000, r=1.000000 |
| I5 | 100.0000 % | 634,300 | R=0.999287, espejo=False, desfase aprendido 180.0° |
| I6′ | 99.7491 % | 634,161 | suma 99.9290 % · contacto⇔Foul/InPlay 99.7491 % · whiff⇒StrikeSwinging 100.0000 % |
| I7 | 86.1167 % | 37,023 | criterio A estricto (n = medias entradas); A sin la final: 86.5887 %; **B (no finales): 91.9790 %**; inconsistentes (≥4 outs): 101; outs por media entrada {'0': 75, '1': 201, '2': 4763, '3': 31883, '4': 84, '5': 8, '6': 7, '8': 1, '9': 1} |
| I8 | 87.5000 % | 8 | tipos: Changeup=✓, Curveball=✓, Cutter=✗ (|HB| mediana D 2.1 / Z 2.2 in), Four-Seam=✓, Sinker=✓, Slider=✓, Splitter=✓, Sweeper=✓ · fallas no informativas (mediana de |HorzBreak| < 2 in en una mano): 0 de 1 |
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

## ADR-012 / ADR-016 — medias entradas de 2 outs registrados: out faltante

Sin orden de lanzamientos, un turno es **incompleto** si hay lanzamientos de un bateador de la media entrada sin ningún evento terminal (lo que dejaría un robo o un pickoff con 2 outs). Si todos sus turnos terminan, la media entrada tiene un **out faltante (sin turno incompleto)**: `OutsOnPlay` no lo cuenta (U) o se perdió con su turno (L). La Prop. 16 de más abajo los separa.

**Clasificación de las 4,449 medias entradas NO finales de 2 outs:** turno incompleto 415 (**9.328 %**) · out faltante (sin turno incompleto) 4,034 (**90.672 %**).

| métrica | 2 outs | 3 outs |
|---|---|---|
| medias entradas | 4,763 | 31,883 |
| % que es la última del juego | 6.592 | 5.228 |
| lanzamientos por media entrada (mediana / media) | 14 / 15.1 | 16 / 17.5 |
| % con ≥1 turno incompleto | 9.469 | 2.948 |
| ponches por out registrado | 0.187 | 0.300 |
| eventos K por media entrada | 0.374 | 0.899 |
| eventos OUT_BIP por media entrada | 1.579 | 1.967 |
| eventos SAC por media entrada | 0.029 | 0.055 |
| eventos BB por media entrada | 0.542 | 0.41 |
| eventos HBP por media entrada | 0.081 | 0.057 |
| eventos ROE por media entrada | 0.057 | 0.046 |
| outs implicados por eventos − OutsOnPlay | {'-2': 3, '-1': 129, '0': 4585, '1': 46} | {'-3': 5, '-2': 116, '-1': 2467, '0': 29118, '1': 173, '2': 3, '3': 1} |

## ADR-016 — ¿outs no contabilizados (U) o turnos perdidos (L)?

**Conjunto T** = medias entradas no finales, `Inning` ≤ 9, consistentes (outs registrados ≤ 3) y sin turno incompleto. `O_h` = Σ `OutsOnPlay`; **P** = {O_h = 2}; `N_h` = turnos con evento 1B, 2B, 3B, BB, HBP o ROE; **Z** = {N_h = 0}. Bajo S1 (un U exige un corredor, luego Z = 0) y S2 (L no depende de Z): r_b = p⁰_b / f_b, con f_b = P(Z | b), p⁰_b = P(P ∧ Z | b) y θ_b = r_b / P(P | b).

| filtro | excluye (en cascada) | no lo cumplen (solo este filtro) | quedan |
|---|---|---|---|
| todas las medias entradas | — | — | 37,023 |
| no es la final del juego | 2,127 | 2,127 | 34,896 |
| Inning ≤ 9 | 358 | 509 | 34,538 |
| consistente (outs < 4) | 95 | 101 | 34,443 |
| sin turno incompleto | 1,376 | 1,523 | 33,067 |

T: 33,067 medias entradas · |P| = 3,998 · |Z| = 9,424 · |P ∧ Z| = 84

### Prop. 16 por cubeta y global (IC95 por bootstrap de 2,123 juegos, 1000 réplicas, semilla 2026)

| cubeta | medias entradas | P % | f_b = Z % | p⁰_b % | **r̂_b %** [IC95] | **θ̂_b** [IC95] |
|---|---|---|---|---|---|---|
| (sin cubeta) | 133 | 14.29 | 21.05 | 0.000 | **0.000** [0.000, 0.000] | **0.000** [0.000, 0.000] |
| Extreme Altitude | 9,366 | 14.81 | 24.90 | 0.246 | **0.986** [0.580, 1.467] | **0.067** [0.039, 0.098] |
| Medium Altitude | 7,844 | 12.30 | 26.38 | 0.191 | **0.725** [0.343, 1.149] | **0.059** [0.029, 0.091] |
| No Altitude | 15,724 | 10.35 | 31.77 | 0.293 | **0.921** [0.659, 1.216] | **0.089** [0.064, 0.116] |
| global | 33,067 | 12.09 | 28.50 | 0.254 | **0.891** [0.710, 1.089] | **0.074** [0.059, 0.090] |

**G0.9 (mecanismo):** θ̂ global = 0.0737 IC95 [0.059, 0.090] → **U** (U si IC95 sup ≤ 0.25 · L si IC95 inf ≥ 0.50 · mezcla en otro caso). Se reporta siempre; no falla.

### Prop. 17 — cota del sesgo del contraste Extreme − No

- m̃_b (turnos por media entrada de T_b): Extreme Altitude 4.6683 · No Altitude 4.3336
- n_b (turnos): Extreme Altitude 43,723 · No Altitude 68,142 · κ̄ (K por turno, global) = 0.18464
- **W(Γ=1) = 0.00423 · W(Γ=2) = 0.00844** · SE_ref = 0.00238 · 3.92·SE_ref = 0.00932 · W(Γ=2)/SE_ref = 3.550
- **G0.8′:** pasa · `perdida_ignorable` = **false** (F8 reporta los contrastes con intervalo de Imbens–Manski)

### Corroboraciones (informativas, no son compuertas)

**(a) Rodados entre los OUT_BIP con `Outs` previo ∈ {0, 1}** (hit_type == GroundBall): U (doble matanza) predice más rodados en P que en T∖P; L, la misma mezcla.

| grupo | n | rodados | % | IC95 Wilson % |
|---|---|---|---|---|
| P | 4,873 | 3,547 | 72.789 | [71.522, 74.02] |
| T∖P | 35,321 | 15,902 | 45.021 | [44.503, 45.541] |

**(b) Columna `Outs` (estado previo), P vs. T∖P.** U no quita lanzamientos: `Outs` es continuo y empieza en 0; L deja huecos o arranca en 1.

| grupo | medias entradas | % mín. Outs > 0 | % out terminal con Outs = 2 | % hueco en Outs |
|---|---|---|---|---|
| P | 3,998 | 2.401 | 39.57 | 36.018 |
| T∖P | 29,069 | 0.083 | 98.191 | 0.378 |

**(c) Logit de 1[h ∈ P]** sobre cubeta + year, sin y con factor(min(N_h, 5)); errores agrupados por juego; OR contra No Altitude (IC95). Si el OR cae al controlar por N_h, la diferencia es tráfico de corredores.

| cubeta | OR sin N_h | OR con N_h |
|---|---|---|
| Extreme Altitude | 1.510 [1.39, 1.63] | 1.426 [1.31, 1.55] |
| Medium Altitude | 1.211 [1.11, 1.32] | 1.146 [1.05, 1.25] |

**(d) Jugadas con `OutsOnPlay` ≥ 2:** 277 en 2,127 juegos; a la tasa MLB de referencia (1.63 dobles matanzas por juego, solo referencia) se esperarían ≈ 3,467: se registra el 8.0 %.

| evento | OutsOnPlay | n |
|---|---|---|
| 1B | 2 | 13 |
| 1B | 3 | 1 |
| 2B | 2 | 4 |
| BB | 2 | 3 |
| BB | 3 | 4 |
| HR | 2 | 1 |
| HR | 3 | 1 |
| NO_TERMINAL | 2 | 17 |
| NO_TERMINAL | 3 | 5 |
| OUT_BIP | 2 | 217 |
| OUT_BIP | 3 | 2 |
| ROE | 2 | 1 |
| SAC | 2 | 8 |

**(e) |P| por juego vs. Poisson** (figura `docs/figuras/f00/P_por_juego_vs_poisson.png`): 2,123 juegos · λ = 1.883 · dispersión de Pearson φ = 1.00 (≈ 1 = evento de juego a tasa constante; ≫ 1 = concentrado en algunos juegos) · P(≥1) observada 0.846 vs Poisson 0.848 · P(>2) 0.294 vs 0.292

### Tablas informativas

**Out faltante (sin turno incompleto) por cubeta** (antiguo G0.8, ya no es compuerta): medias entradas no finales, IC de Wilson al 95 %. Mezcla U y L; la Prop. 16 los separa.

| cubeta | medias_entradas | dos_outs | turno_incompleto | out_faltante | tasa_% | ic95_wilson_% |
|---|---|---|---|---|---|---|
| (sin cubeta) | 153 | 22 | 1 | 21 | 13.725 | [9.156, 20.072] |
| Extreme Altitude | 9,799 | 1,476 | 78 | 1,398 | 14.267 | [13.588, 14.973] |
| Medium Altitude | 8,332 | 1,091 | 115 | 976 | 11.714 | [11.041, 12.422] |
| No Altitude | 16,612 | 1,860 | 221 | 1,639 | 9.866 | [9.422, 10.329] |

Rango entre cubetas (máx − mín): 4.400 pp

**Por cubeta y año:**

| cubeta | year | medias_entradas | out_faltante | tasa_% | ic95_wilson_% |
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

**Déficits de eventos** (media por media entrada de las de 3 outs − media de las de 2 outs; IC95 por bootstrap de medias entradas). Informativos: el estimador de la fracción de ponches por déficits se retiró (ADR-016: no está identificado; D01 resuelta). No se implementan pesos ω (F4).

- **todas las de 2 outs** (n = 4,763 vs 31,883): d_K = 0.525 [0.506, 0.542] · d_OUT_BIP = 0.387 [0.370, 0.407] · d_SAC = 0.026 [0.021, 0.032]
- **solo las de out faltante sin turno incompleto** (n = 4,312 vs 31,883): d_K = 0.538 [0.519, 0.556] · d_OUT_BIP = 0.363 [0.344, 0.383] · d_SAC = 0.028 [0.022, 0.033]

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
- **G0.3** ✅ diagnóstico de las 4,763 medias entradas de 2 outs producido y clasificado (no finales: 4,449): turno incompleto 9.328 % vs out faltante (sin turno incompleto) 90.672 %
- **G0.4** ✅ I9 100.0000 % de 2,117 juegos con cubeta
- **G0.5** ✅ valores sin regla: 0
- **G0.6** ✅ excluir_modelo 0.803 % (máx. 3%) · excluir_cadena 0.135 % (máx. 0.5%)
- **G0.7** ✅ ADR-014 con y_p = 1.4167 ft y signo -1: |error| mediana/p99 PlateLocSide 0.0017/0.0091 ft · PlateLocHeight 0.0013/0.0318 ft (máx. 0.05/0.3) · |ZoneTime − (t_p − t_s)| mediana 0.00003 s (máx. 0.005) · config vigente coincide
- **G0.8′** ✅ Prop. 17: W(Γ=1) 0.0042 · **W(Γ=2) 0.0084** vs 3.92·SE_ref = 0.0093 y 1·SE_ref = 0.0024 (κ̄ 0.1846, n Extreme Altitude 43,723 / No Altitude 68,142) · r̂ Extreme Altitude 0.9863 % / No Altitude 0.9209 % · **perdida_ignorable = false**
- **G0.9** ✅ θ̂ global = 0.0737 IC95 [0.059, 0.090] → **U** (U si sup ≤ 0.25 · L si inf ≥ 0.5 · mezcla en otro caso); se reporta siempre, no falla

### Bloque para el orquestador — F00
- Modelo(s) usado(s): Sonnet
- Compuertas: G0.1 ✅ | G0.2 ✅ | G0.3 ✅ | G0.4 ✅ | G0.5 ✅ | G0.6 ✅ | G0.7 ✅ | G0.8′ ✅ | G0.9 ✅
- Cifras clave: 635,002 lanzamientos · 2,127 juegos · excluir_modelo 0.8035 % · excluir_cadena 0.1348 % · I1 100.0000 % · I6′ 99.7491 % · I7 A 86.1167 % / B no finales 91.9790 % · ADR-010: equivalentes · t_s mediana -0.0363 s · ADR-014 y_p 1.4167 ft, signo -1, |ZoneTime−(t_p−t_s)| mediana 0.00003 s · ADR-016: θ̂ 0.074 [0.059, 0.090] → **U** · r̂ por cubeta: (sin cubeta) 0.0000 %, Extreme Altitude 0.9863 %, Medium Altitude 0.7250 %, No Altitude 0.9209 % · W(Γ=2) 0.00844 vs 3.92·SE_ref 0.00932 (SE_ref 0.00238) · perdida_ignorable false
- Desviaciones respecto al ROADMAP: ninguna (compuertas v2.6: G0.8′ y G0.9 de ADR-016)
- Mejora posible detectada: ninguna
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase00 / (pendiente) / (pendiente)
- Log: reports/logs/f00_<fecha>.log
