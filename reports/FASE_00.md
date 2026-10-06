# FASE 00 — Ingesta y QA por identidades

Filas de entrada: 635,002 · filas de salida: 635,002 · 4.6s

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
| Walk | StrikeCalled | Walk | BB | 1 |
| Out | BallCalled | Undefined | — | 1 |

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

## ADR-010 — ejes de los polinomios de trayectoria vs. los 9P

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

- Mejor permutación con signo (R² mínimo sobre c2 y c1): {'X': 'y', 'Y': 'z', 'Z': 'x'} · signos {'X': 1, 'Y': 1, 'Z': 1} · R² mín. **0.988868** (exigido 0.99)
- Escala |2·pendiente(c2)| (1 = misma escala): {'X': '1.0000', 'Y': '1.0000', 'Z': '1.0000'}
- **Decisión: `no_canonicos`** — ninguna permutación con signo alcanza el R² exigido: se declaran no canónicos y no se usan.

Regresión conjunta (informativa): cada eje del polinomio sobre los tres ejes de los 9P a la vez. Si R² ≈ 1 con coeficientes que no son ±1 y 0, los polinomios están en un marco **rotado**, no son una permutación con signo.

| familia | eje del polinomio | R² | coef. sobre (x, y, z) | intercepto |
|---|---|---|---|---|
| c2 | X | 1.000000 | (+0.0000, +0.5000, -0.0000) | -0.0000 |
| c2 | Y | 1.000000 | (-0.0000, +0.0000, +0.5000) | -0.0000 |
| c2 | Z | 1.000000 | (+0.5000, +0.0000, -0.0000) | -0.0000 |
| c1 | X | 0.999701 | (+0.0006, +1.0013, -0.0017) | -0.6961 |
| c1 | Y | 0.995333 | (+0.0031, +0.0343, +1.0271) | 5.3374 |
| c1 | Z | 0.998100 | (+1.0345, -0.0087, +0.0024) | -1.0875 |
| c0 | X | 0.004739 | (+0.0232, -2815.7412, +0.0200) | 140841.6074 |
| c0 | Y | 0.955410 | (+0.0001, +923.7797, +1.0591) | -46189.2228 |
| c0 | Z | 0.996996 | (+1.1103, +554.2823, +0.0131) | -27714.1947 |

**Verificación de la trayectoria canónica (9P):** posición en t = ZoneTime contra el dato (n = 635,002; |error| en pies, mediana / p99): PlateLocSide 1.2897 / 5.0899 · PlateLocHeight 0.4717 / 1.0554 · y(ZoneTime) − 17/12 ft 4.2740 / 5.3908

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
| es_bip | 0 | is_ball_in_play | 1 | BallCalled | 1 |
| es_bip | 0 | is_ball_in_play | 1 | StrikeSwinging | 1 |

## ADR-012 — medias entradas de 2 outs (diagnóstico)

Candidatos: (1) tercer out sin lanzamiento propio (robo, pickoff) → la media entrada deja un turno **incompleto**; (2) lanzamientos faltantes; (3) `OutsOnPlay` que no cuenta ciertos outs. Sin orden de lanzamientos, el último turno reconstruible es el del bateador sin evento terminal.

| métrica | 2 outs | 3 outs |
|---|---|---|
| medias entradas | 4,763 | 31,883 |
| % que es la última del juego | 6.592 | 5.228 |
| lanzamientos por media entrada (mediana / media) | 14 / 15.1 | 16 / 17.5 |
| % con ≥1 turno incompleto | 9.469 | 2.948 |
| turnos incompletos por media entrada | 0.0989 | 0.0300 |
| eventos K por media entrada | 0.374 | 0.899 |
| eventos OUT_BIP por media entrada | 1.579 | 1.967 |
| eventos SAC por media entrada | 0.029 | 0.055 |
| eventos BB por media entrada | 0.542 | 0.41 |
| eventos HBP por media entrada | 0.081 | 0.057 |
| eventos ROE por media entrada | 0.057 | 0.046 |
| outs implicados por eventos − OutsOnPlay | {'-2': 3, '-1': 129, '0': 4585, '1': 46} | {'-3': 5, '-2': 116, '-1': 2467, '0': 29118, '1': 173, '2': 3, '3': 1} |

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
- **G0.2** ✅ matriz 3×3 producida · ningún mapeo con R² ≥ 0.99 (mejor R² mín. 0.988868) → ADR-010: polinomios NO canónicos · la trayectoria canónica es la de los 9P
- **G0.3** ❌ criterio B 91.9790 % de 34,896 medias entradas no finales (mín. 95%) · diagnóstico de las de 2 outs: producido (4,763 medias entradas)
- **G0.4** ✅ I9 100.0000 % de 2,117 juegos con cubeta
- **G0.5** ✅ valores sin regla: 0
- **G0.6** ✅ excluir_modelo 0.803 % (máx. 3%) · excluir_cadena 0.135 % (máx. 0.5%)

### Bloque para el orquestador — F00
- Modelo(s) usado(s): Sonnet
- Compuertas: G0.1 ✅ | G0.2 ✅ | G0.3 ❌ | G0.4 ✅ | G0.5 ✅ | G0.6 ✅
- Cifras clave: 635,002 lanzamientos · 2,127 juegos · excluir_modelo 0.8035 % · excluir_cadena 0.1348 % · I1 100.0000 % · I6′ 99.7491 % · I7 A 86.1167 % / B no finales 91.9790 % · ADR-010: no_canonicos
- Desviaciones respecto al ROADMAP: ninguna (compuertas v2.4, ADR-010 a 013)
- Mejora posible detectada: ninguna
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase00 / (pendiente) / (pendiente)
- Log: reports/logs/f00_<fecha>.log
