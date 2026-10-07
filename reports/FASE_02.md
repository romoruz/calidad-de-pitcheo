# FASE 02 — Densidad del aire por juego desde la trayectoria

635,002 filas de entrada · 629,820 lanzamientos válidos · 215.0s

## Datos y estimador (Prop. 1 y Prop. 2′)

| paso | filas |
|---|---|
| filas_entrada | 635,002 |
| excluir_modelo | 5,102 |
| familia_EXC | 0 |
| id_nulo | 0 |
| fisica_nula | 80 |
| t_s_t_p_o_rho_no_positiva | 0 |
| filas_salida | 629,820 |

**Conjunto conectado** (grafo juegos–lanzador×forma, Abowd–Kramarz–Margolis): 2,122 de 2,122 juegos · 5,647 de 5,647 lanzador×forma · 629,648 de 629,648 filas · componentes 1. Los juegos fuera del gigante no tienen δ_g identificado.

Juegos: 2,122 con δ̂ · 2,112 confirmatorios · 6 sin cubeta (🔎, fuera de la normalización y de G2.2) · 4 de baja confianza (n efectivo < n_min en el soporte común).

**Solver** (LSMR disperso, Fong y Saunders 2011; equivale a las proyecciones alternadas a ≤ 1e-8, prueba de regresión): δᴰ: 471 iteraciones, convergió=True, residuo normal relativo 1.7e-14 · δᴸ: 468 iteraciones, convergió=True, residuo normal relativo 3.9e-14

Soporte común de S entre cubetas: 581,599 de 629,648 filas dentro; estratos sin soporte común: ninguno.

f_D: 36 estratos forma×mano×year; tipo de base por estrato: {'spline': 36}.

## δ̂ por cubeta (G2.2)

| cubeta | juegos | δ̄ᴰ | EE (2 vías) | ρ̂/ρ_ref | δ̄ᴸ |
|---|---|---|---|---|---|
| No Altitude | 1001 | -0.0001 | 0.0015 | 0.9999 | -0.0011 |
| Medium Altitude | 508 | -0.1008 | 0.0023 | 0.9041 | -0.1941 |
| Extreme Altitude | 603 | -0.1589 | 0.0019 | 0.8531 | -0.2719 |

**Contrastes (media, EE de dos vías juego × lanzador):** Medium Altitude − No Altitude: -0.1006 ± 0.0028 · Extreme Altitude − No Altitude: -0.1588 ± 0.0024

**Mezcla gaussiana de Extreme (BIC → 1 componentes):** media -0.1589 (sd 0.0394, peso 1.00). La de menor media es la de menor densidad: define ρ_CDMX (ADR-005).

### δ̄ contra log ρ barométrica (ROADMAP §2) — informativo

| cubeta | altitud_m | log ρ_baro | δ̄ᴰ | EE |
|---|---|---|---|---|
| No Altitude | 20 | 0.0000 | -0.0001 | 0.0015 |
| Medium Altitude | 532 | -0.0611 | -0.1008 | 0.0023 |
| Extreme Altitude | 2000 | -0.2403 | -0.1589 | 0.0019 |

Pendiente de δ̄ᴰ sobre log ρ barométrica: **0.631** (IC95 [0.611, 0.650]); 3 puntos, pesos 1/EE²; altitudes representativas ilustrativas: informativo, no es compuerta.

### δ̄ de la cubeta de referencia por año (diagnóstico)

La normalización es global; el nivel de cada año (cambio de pelota) lo absorbe δ_g. Si estos valores difieren más de ~0.01 entre años, las medias por cubeta mezclan años con composición distinta (🔎).

2024: -0.0177 · 2025: +0.0177 · 2026: +0.0017

## Sobreidentificación: Deming δ^L sobre δ^D (G2.3)

Pendiente **1.514** (EE dos vías 0.019; z vs 1 = 26.55), intercepto -0.0194 (EE 0.0021), razón de varianzas de error 12.526, 2,112 juegos. Banda de G2.3: [0.85, 1.15].

## σ_η y SE de δ̂_g (G2.4)

σ_η = **0.0774** (log ρC_D) y **0.2810** (log ρC_L). SE de δ̂_g con CR2 (conglomerados = lanzador dentro del juego; CR2): mediana **0.0105** (D), 0.0375 (L); ingenuo σ_η/√n_g: 0.0045; efecto de diseño ×2.34.

## Prop. 3′: ĉ_g por juego (residuo de calibración c_g·g)

**SpinAxis:** SpinAxis medido: se usa el detector ê (desfase RMS con el eje que implica el movimiento nan°, umbral 1.0°; sd de ã·ê dentro de lanzador×forma nan m/s², umbral 0.05; R² de SpinAxis sobre las columnas de movimiento, dentro de lanzador×forma, nan (inferido si ≥ 0.95); signo lateral σ = +1).

ĉ_g = (δ̂ᴸ − δ̂ᴰ − media_ref)/κ̄ con κ̄ = -1.294 (sensibilidad media de log ρC_L a c). Relativo a la cubeta de referencia, como δ: el nivel común de c lo absorbe f_L. **Lectura:** (i) hay un sesgo de línea base por ruido de medición que depende de ρ; (ii) en este canal el factor de giro S también se calcula con la v medida, lo que contamina ĉ con η_S·log(λ/τ). Ver D02b y la tabla de escenarios sintéticos.

**ĉ_g por cubeta, (δ̂ᴸ − δ̂ᴰ)/κ̄:**

| cubeta | juegos | media | sd | p05 | mediana | p95 |
|---|---|---|---|---|---|---|
| Extreme Altitude | 603 | 0.0873 | 0.0438 | 0.0184 | 0.0848 | 0.1615 |
| Medium Altitude | 508 | 0.0721 | 0.0388 | 0.0105 | 0.0717 | 0.1356 |
| No Altitude | 1001 | 0.0008 | 0.0404 | -0.0641 | 0.0009 | 0.0675 |

**ĉ_g por cubeta, detector ê:**

| cubeta | juegos | media | sd | p05 | mediana | p95 |
|---|---|---|---|---|---|---|
| Extreme Altitude | 506 | -0.0001 | 0.0005 | -0.0009 | -0.0001 | 0.0008 |
| Medium Altitude | 489 | -0.0002 | 0.0005 | -0.0011 | -0.0003 | 0.0006 |
| No Altitude | 944 | -0.0000 | 0.0011 | -0.0014 | -0.0002 | 0.0021 |

**ĉ_ê por parque, centrado en la mediana de su cubeta (G2.3b sobre los datos; parque latente 🔎 (mezcla gaussiana de δ̂ᴰ por cubeta; no es un parque identificado); SE CR2; Wald + BH al 5 %):** 0 de 0 parques evaluados marcados.

| parque | cubeta | ĉ crudo | ĉ centrado | SE CR2 | z | BH |
|---|---|---|---|---|---|---|
| Extreme Altitude|0 | Extreme Altitude | — | — | — | — | n/e |
| Medium Altitude|0 | Medium Altitude | — | — | — | — | n/e |
| No Altitude|0 | No Altitude | — | — | — | — | n/e |

Un parque marcado significa |ĉ| distinto del de su cubeta (calibración distinta de la mediana de los parques de su altitud): se revisa, no se descarta. El centrado absorbe el sesgo de línea base que depende de ρ (D02b §3).

## Parques latentes (🔎 exploratorio)

Mezcla gaussiana con BIC sobre δ̂ᴰ_g dentro de cada cubeta (juegos confirmatorios). No es estadístico de H1–H6.

- **Extreme Altitude:** 1 componentes · -0.159 (sd 0.039, peso 1.00)
- **Medium Altitude:** 1 componentes · -0.101 (sd 0.042, peso 1.00)
- **No Altitude:** 1 componentes · -0.000 (sd 0.043, peso 1.00)

**rel_height_residual_ft por cubeta (media por juego):** Extreme Altitude: 0.0093 ± 0.0713 · Medium Altitude: -0.0166 ± 0.0903 · No Altitude: 0.0015 ± 0.0839

**sesgo_plateloc_height_ft por cubeta (media por juego):** Extreme Altitude: 0.0067 ± 0.0042 · Medium Altitude: 0.0068 ± 0.0049 · No Altitude: 0.0064 ± 0.0051

**Juegos sin cubeta (6) — cubeta más verosímil según δ̂ᴰ (🔎):** {'Extreme Altitude': 6}

## Sintética con física exacta: estudio de simulación de G2.1 (ADR-017)

`solve_ivp` DOP853 (rtol 1e-10), ρ conocida en 3 niveles (1.00, 0.82, 0.76·ρ₀), C_D y C_L realistas, ruido de posición, 9P de aceleración constante ajustado por mínimos cuadrados, efecto de lanzador α_j (SD 0.05 en log C_D) con planteles asignados a parques locales. **Protocolo pre-registrado** (Morris, White y Crowther 2019): R = 10 réplicas independientes, semillas 101–110, 150 juegos × ≈250 lanzamientos (≈37,451 por réplica), estimando log(ρ_nivel/ρ_No). Aprueba si, por nivel, |sesgo relativo medio| + 1.96·MCSE < 1 %.

| nivel | sesgo relativo medio | MCSE | |sesgo| + 1.96·MCSE | veredicto | SE empírico δ̂ | RMSE δ̂ | cobertura IC95 CR2 | juegos×réplicas |
|---|---|---|---|---|---|---|---|---|
| Medium Altitude | +0.126 % | 0.069 % | 0.261 % | ✓ | 0.0084 | 0.0085 | 0.961 | 389 |
| Extreme Altitude | +0.001 % | 0.073 % | 0.145 % | ✓ | 0.0084 | 0.0084 | 0.960 | 427 |

**Cobertura del IC95 CR2 de δ̂_g sobre todos los juegos × réplicas (1,500): 0.965**. σ_η medio 0.0521. Errores por réplica (Medium / Extreme): +0.13 % / -0.02 %; +0.52 % / +0.18 %; -0.30 % / -0.50 %; -0.06 % / +0.01 %; +0.09 % / +0.14 %; +0.08 % / -0.32 %; +0.07 % / +0.12 %; +0.33 % / +0.11 %; +0.24 % / +0.17 %; +0.15 % / +0.12 %.

**Planteles locales** (semilla 101): RMSE de δ̂ contra la verdad 0.0207 sin α_{j,k} → 0.0069 con α_{j,k} (Prop. 2′): el segundo efecto fijo elimina el sesgo del C_D medio del plantel.

## Sintética de calibración para G2.3b (ADR-017, F2.5b)

18 parques (6 por cubeta); en cada cubeta λ = 1.02 en 2 parques, τ = 1.01 en otros 2 y 2 limpios (c = λ/τ² − 1 ≈ ±0.02). 300 juegos × ≈250 lanzamientos por réplica, R = 10 (semillas 101–110). Detector ê con id de parque, centrado en la mediana de la cubeta, Wald con SE CR2 y BH al 5 %. **Diseño y tamaño fijados antes de la corrida final** (solo se usaron las semillas 101–102 para medir tiempo y SE del detector).

| grupo de parques | parques×réplicas | marcados por BH | tasa | ĉ centrado medio | c verdad | SE CR2 medio |
|---|---|---|---|---|---|---|
| λ = 1.02 (c≈+0.02) | 60 | 60 | 1.000 | 0.0200 | 0.0200 | 0.0016 |
| τ = 1.01 (c≈−0.02) | 60 | 60 | 1.000 | -0.0197 | -0.0197 | 0.0016 |
| limpios (c=0) | 60 | 10 | 0.167 | 0.0000 | 0.0000 | 0.0010 |

**Potencia (contaminados) 1.000** (mínimo 0.8, y también por tipo) · **FPR (limpios) 0.167** (máximo 0.05). Control sin calibración (todos los parques limpios, mismas semillas): 1 de 180 parques marcados, FPR 0.006. Con 2 parques limpios por cubeta la mediana es su promedio, así que los contrastes de cada par son iguales y de signo opuesto: los falsos positivos llegan de a pares.

**G2.3a en la sintética (informativo):** pendiente de Deming media 1.021 con calibración por parque contra 1.010 sin ella; la banda [0.85, 1.15] no distingue ambas (D02b).

## Compuertas

- **G2.1** ✅ estudio de simulación, R = 10 réplicas (semillas 101–110), |sesgo relativo medio| + 1.96·MCSE por nivel < 1 %: Medium +0.126 % + 1.96×0.069 % = 0.261 % ✓ · Extreme +0.001 % + 1.96×0.073 % = 0.145 % ✓ (peor nivel 0.261 %)
- **G2.2** ❌ (a) orden estricto ✓: δ̄ No -0.0001 > Medium -0.1008 > Extreme -0.1589 · (b) δ̄ Extreme ∈ [-0.3, -0.15]: ✓ · (c) componente de menor media de la mezcla de Extreme -0.1589 ∈ [-0.32, -0.2]: ✗
- **G2.3a** ❌ Deming δ^L sobre δ^D: pendiente 1.514 (EE dos vías 0.019) ∈ [0.85, 1.15] · intercepto -0.0194
- **G2.3b** ❌ detector ê por parque (Wald CR2 + BH 5 %), 10 réplicas × 18 parques: potencia 1.000 (λ=1.02: 1.000, 60/60; τ=1.01: 1.000, 60/60; mínimo 0.8) · FPR en parques limpios 0.167 (10/60; máximo 0.05)
- **G2.4** ✅ σ_η = 0.0774 (D) / 0.2810 (L) · SE CR2 mediano de δ̂_g = 0.0105 (límite 0.03; ingenuo 0.0045, efecto de diseño ×2.34) · método CR2 · cobertura del IC95 CR2 en la sintética 0.965 (mínimo 0.9) ✓

Figuras agregadas por juego en `docs/figuras/f2/`: delta_por_cubeta.png, deming_delta_L_vs_D.png, c_g_por_cubeta.png.

### Bloque para el orquestador — F02
- Modelo(s) usado(s): Sonnet (implementación)
- Compuertas: G2.1 ✅ | G2.2 ❌ | G2.3a ❌ | G2.3b ❌ | G2.4 ✅
- Cifras clave: δ̄ᴰ No -0.0001 · Medium -0.1008 ± 0.0023 · Extreme -0.1589 ± 0.0019 · Deming 1.514 · σ_η 0.0774 · SE CR2 mediano 0.0105 · G2.1 0.261 % (|sesgo|+1.96 MCSE, peor nivel) · cobertura IC95 0.965 · G2.3b potencia 1.00 / FPR 0.167 · 2,112 juegos confirmatorios
- Desviaciones respecto al ROADMAP: ninguna en las compuertas; la cobertura ≥ 0.90 se trata como condición de G2.4 (ADR-017 la daba como alerta)
- Mejora posible detectada: 🔎 D02b — con el detector ê escala y reloj son separables; la banda de G2.3a no detecta 2 %
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase02 / (pendiente) / (pendiente)
- Log: reports/logs/f02_<fecha>.log
