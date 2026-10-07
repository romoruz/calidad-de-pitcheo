# FASE 02 — Densidad del aire por juego desde la trayectoria

635,002 filas de entrada · 629,820 lanzamientos válidos · 161.0s

> **FASE DETENIDA (ADR-019):** la equivalencia (1+β̂_L)/(1+β̂_D) contra la Deming observada NO pasa; G2.2–G2.4 se reportan en bruto con 🔎 (provisionales) y no se avanza. Ver la sección de Prop. 2″.

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

**Solver** (LSMR disperso, Fong y Saunders 2011; equivale a las proyecciones alternadas a ≤ 1e-8, prueba de regresión): δᴰ: 471 iteraciones, convergió=True, residuo normal relativo 1.8e-14 · δᴸ: 469 iteraciones, convergió=True, residuo normal relativo 3.3e-14

Soporte común de S entre cubetas: 581,599 de 629,648 filas dentro; estratos sin soporte común: ninguno.

f_D: 36 estratos forma×mano×year; tipo de base por estrato: {'spline': 36}.

## δ̂ por cubeta (G2.2)

| cubeta | juegos | δ̄ᴰ | EE (2 vías) | ρ̂/ρ_ref | δ̄ᴸ |
|---|---|---|---|---|---|
| No Altitude | 1001 | -0.0002 | 0.0014 | 0.9998 | -0.0012 |
| Medium Altitude | 508 | -0.1014 | 0.0022 | 0.9036 | -0.1952 |
| Extreme Altitude | 603 | -0.1597 | 0.0018 | 0.8524 | -0.2712 |

**Contrastes (media, EE de dos vías juego × lanzador):** Medium Altitude − No Altitude: -0.1012 ± 0.0026 · Extreme Altitude − No Altitude: -0.1596 ± 0.0023

**Mezcla gaussiana de Extreme (BIC → 1 componentes):** media -0.1597 (sd 0.0386, peso 1.00). La de menor media es la de menor densidad: define ρ_CDMX (ADR-005).

### δ̄ contra log ρ barométrica (ROADMAP §2) — informativo

| cubeta | altitud_m | log ρ_baro | δ̄ᴰ | EE |
|---|---|---|---|---|
| No Altitude | 20 | 0.0000 | -0.0002 | 0.0014 |
| Medium Altitude | 532 | -0.0611 | -0.1014 | 0.0022 |
| Extreme Altitude | 2000 | -0.2403 | -0.1597 | 0.0018 |

Pendiente de δ̄ᴰ sobre log ρ barométrica: **0.638** (IC95 [0.619, 0.656]); 3 puntos, pesos 1/EE²; altitudes representativas ilustrativas: informativo, no es compuerta.

### δ̄ de la cubeta de referencia por año (diagnóstico)

La normalización es global; el nivel de cada año (cambio de pelota) lo absorbe δ_g. Si estos valores difieren más de ~0.01 entre años, las medias por cubeta mezclan años con composición distinta (🔎).

2024: +0.0000 · 2025: -0.0000 · 2026: +0.0000

## Sobreidentificación: Deming δ^L sobre δ^D (G2.3)

Pendiente **1.556** (EE dos vías 0.018; z vs 1 = 30.34), intercepto -0.0159 (EE 0.0018), razón de varianzas de error 9.381, 2,112 juegos. Banda de G2.3: [0.85, 1.15].

## σ_η y SE de δ̂_g (G2.4)

σ_η = **0.0774** (log ρC_D) y **0.2810** (log ρC_L). SE de δ̂_g con CR2 (conglomerados = lanzador dentro del juego; CR2): mediana **0.0089** (D), 0.0256 (L); ingenuo σ_η/√n_g: 0.0045; efecto de diseño ×1.98.

## Prop. 2″ (ADR-018/019): corrección de atenuación por Reynolds

Modelo `y_c = δ_g + α_jk + f_c(S) + β_c · log‖v̄‖ + ε`; estimador: 2SLS con log(RelSpeed) como instrumento de log‖v̄‖ (la rapidez en la liberación se mide antes del vuelo y es exógena al arrastre del propio lanzamiento; con MCO, log‖v̄‖ queda correlacionado con el error porque un C_D mayor frena más: sesgo de endogeneidad, ADR-019); spline de S con S_rel = rω/RelSpeed (exógena). SE: sándwich CR2 por lanzador×juego sobre la segunda etapa con residuo estructural. **β̂_D = -0.148 ± 0.008**, **β̂_L = +0.618 ± 0.040** (MCO sin instrumento, diagnóstico: β̂_D = -0.761, β̂_L = +0.381). Primera etapa: corr. parcial 0.985, F = 20,518,035 (instrumento fuerte si F > 10). R² de log‖v̄‖ sobre {dummies de juego, lanzador×forma, splines de S} = **0.902** (tope 0.98; identificable: ✓).

**Prueba de sobreidentificación** (pendiente predicha vs Deming observada, equivalencia ±tol; en datos reales DECIDE qué es primario):

| pendiente predicha (1+β_L)/(1+β_D) | Deming observada | diferencia | SE(diferencia) | |dif|+1.96·SE | tolerancia | equivalencia |
|---|---|---|---|---|---|---|
| 1.897 | 1.556 | 0.342 | 0.054 | 0.447 | 0.10 | ✗ |

**Adopción (ADR-019):** ✗ NO adoptado: G2.2–G2.4 se reportan en bruto con 🔎 (provisional) y la fase SE DETIENE. Convergió: [True, True].

## Prop. 3′: ĉ_g por juego (residuo de calibración c_g·g)

**SpinAxis:** SpinAxis INFERIDO del movimiento: el único detector es G2.3a (Deming) (desfase RMS con el eje que implica el movimiento 1.17°, umbral 1.0°; sd de ã·ê dentro de lanzador×forma 0.013 m/s², umbral 0.05; R² de SpinAxis sobre las columnas de movimiento, dentro de lanzador×forma, 0.998 (inferido si ≥ 0.95); signo lateral σ = +1).

ĉ_g = (δ̂ᴸ − δ̂ᴰ − media_ref)/κ̄ con κ̄ = -1.294 (sensibilidad media de log ρC_L a c). Relativo a la cubeta de referencia, como δ: el nivel común de c lo absorbe f_L. **Lectura:** (i) hay un sesgo de línea base por ruido de medición que depende de ρ; (ii) en este canal el factor de giro S también se calcula con la v medida, lo que contamina ĉ con η_S·log(λ/τ). Ver D02b y la tabla de escenarios sintéticos.

**ĉ_g por cubeta, (δ̂ᴸ − δ̂ᴰ)/κ̄:**

| cubeta | juegos | media | sd | p05 | mediana | p95 |
|---|---|---|---|---|---|---|
| Extreme Altitude | 603 | 0.0861 | 0.0406 | 0.0227 | 0.0847 | 0.1553 |
| Medium Altitude | 508 | 0.0725 | 0.0360 | 0.0130 | 0.0742 | 0.1297 |
| No Altitude | 1001 | 0.0008 | 0.0377 | -0.0587 | 0.0006 | 0.0607 |

_El detector ê sobre datos reales es n/e: SpinAxis sale inferido del movimiento (prueba de circularidad, ADR-017). Datos: n_evaluado = 629208 de 629648, R² = 0.9976, sd(ã·ê) = 0.0133, desfase = 1.17°. El único detector de calibración sobre real es G2.3a._

## Parques latentes (🔎 exploratorio)

Mezcla gaussiana con BIC sobre δ̂ᴰ_g dentro de cada cubeta (juegos confirmatorios). No es estadístico de H1–H6.

- **Extreme Altitude:** 1 componentes · -0.160 (sd 0.039, peso 1.00)
- **Medium Altitude:** 1 componentes · -0.101 (sd 0.040, peso 1.00)
- **No Altitude:** 1 componentes · -0.000 (sd 0.040, peso 1.00)

**rel_height_residual_ft por cubeta (media por juego):** Extreme Altitude: 0.0093 ± 0.0713 · Medium Altitude: -0.0166 ± 0.0903 · No Altitude: 0.0015 ± 0.0839

**sesgo_plateloc_height_ft por cubeta (media por juego):** Extreme Altitude: 0.0067 ± 0.0042 · Medium Altitude: 0.0068 ± 0.0049 · No Altitude: 0.0064 ± 0.0051

**Juegos sin cubeta (6) — cubeta más verosímil según δ̂ᴰ (🔎):** {'Extreme Altitude': 6}

## Sintética con física exacta: estudio de simulación de G2.1 (ADR-017/019)

`solve_ivp` DOP853 (rtol 1e-10), ρ conocida en 3 niveles (1.00, 0.82, 0.76·ρ₀), **C_D = C_D(Re) con ley potencial pura (pendiente local en log Re = β_D = -0.3, sin ningún otro término en v; ADR-019 D1)**, C_L(S) sin Re (β_L = 0.0), ruido de posición, 9P de aceleración constante por mínimos cuadrados, efecto de lanzador α_j (SD 0.05 en log C_D) con planteles asignados a parques locales. **Protocolo pre-registrado** (Morris, White y Crowther 2019): R = 30 réplicas independientes, semillas 211–240 (**las semillas 101–110 y 201–210 están consumidas**: D02b §4 y D02c §8), 150 juegos × ≈250 lanzamientos (≈37,471 por réplica), estimando log(ρ_nivel/ρ_No). Aprueba si, por nivel, |sesgo relativo medio| + 1.96·MCSE < 1 %. Réplicas leídas de la caché: 30 de 30.

**Primario de G2.1 (δ̃)**: δ̃ = δ̂/(1+β̂) con β̂ por 2SLS (Prop. 2″, ADR-018/019); se reporta además el bruto como demostración de la atenuación.

| nivel | sesgo relativo medio | MCSE | |sesgo| + 1.96·MCSE | veredicto | SE empírico δ̃ | RMSE δ̃ | cobertura IC95 | juegos×réplicas |
|---|---|---|---|---|---|---|---|---|
| Medium Altitude | -0.146 % | 0.081 % | 0.305 % | ✓ | 0.0065 | 0.0067 | 0.971 | 1151 |
| Extreme Altitude | -0.188 % | 0.113 % | 0.410 % | ✓ | 0.0080 | 0.0082 | 0.967 | 1245 |

**Demostración de la atenuación (δ̂ bruto, sin corregir)** con β_D explícito en el generador:

| nivel | sesgo bruto | |sesgo|+1.96·MCSE bruto | cobertura bruto | RMSE bruto |
|---|---|---|---|---|
| Medium Altitude | +5.940 % | 5.976 % | 0.000 | 0.0578 |
| Extreme Altitude | +8.327 % | 8.363 % | 0.000 | 0.0800 |

**β̂ en el estudio** (R = 30, estimador IV): β̂_D = -0.304 ± 0.016 (SE medio 0.020; verdad -0.3), β̂_L = -0.015 ± 0.032 (verdad 0.0). MCO sin instrumento: β̂_D = -0.562 (sesgo por endogeneidad de log‖v̄‖, ADR-019). R² de colinealidad log‖v̄‖ medio = 0.957.

**Equivalencia de pendientes (informativa, no es compuerta en la sintética):** predicha (1+β̂_L)/(1+β̂_D) = 1.416 contra Deming observada 1.410; aprueban ±0.1: 0 de 30 réplicas.

**Cobertura del IC95 de δ̃_g (SE delta method con Var(β̂) si primario δ̃) sobre todos los juegos × réplicas (4,500): 0.948**. σ_η medio (bruto) 0.0498. Errores por réplica (Medium / Extreme): -0.52 % / -0.64 %; +0.09 % / +0.05 %; -0.02 % / -0.14 %; -0.37 % / -0.35 %; -0.28 % / -0.59 %; -0.57 % / -0.97 %; -0.63 % / -0.68 %; -0.49 % / -0.40 %; -0.43 % / -0.57 %; -0.57 % / -0.60 %; -0.73 % / -1.07 %; -0.74 % / -0.94 %; -0.15 % / -0.33 %; +0.21 % / +0.44 %; -0.60 % / -0.64 %; +0.42 % / +0.90 %; +0.44 % / +0.53 %; -0.14 % / -0.34 %; -0.30 % / -0.57 %; -0.35 % / -0.73 %; -0.11 % / +0.08 %; -0.16 % / -0.16 %; +0.66 % / +0.87 %; -0.10 % / -0.35 %; +0.13 % / +0.19 %; +0.32 % / +0.55 %; +0.01 % / -0.11 %; -0.72 % / -0.93 %; +1.01 % / +1.39 %; +0.33 % / +0.47 %.

**Planteles locales** (semilla 211): RMSE de δ̂ contra su estimando (1+β_D)·log ρ 0.0201 sin α_{j,k} → 0.0037 con α_{j,k} (Prop. 2′): el segundo efecto fijo elimina el sesgo del C_D medio del plantel.

## Sintética de calibración para G2.3b (ADR-018/019, F2.5b)

18 parques (6 por cubeta); en cada cubeta λ = 1.02 en 2 parques, τ = 1.01 en otros 2 y 2 limpios (c = λ/τ² − 1 ≈ ±0.02). 300 juegos × ≈250 lanzamientos por réplica, R = 30 (semillas 211–240). Detector ê con id de parque: contraste LOO (c_p − media del resto de la cubeta), cluster = lanzador, t de Pustejovsky y Tipton (2018) y BH al 5 %. Criterio (ADR-019 D3): potencia ≥ 0.8 y FPR ≤ 0.05 + 1.96·√(0.05·0.95/n_limpios) = 0.0818 (n_limpios = 180; Morris, White y Crowther 2019 §5.2), con IC de Clopper–Pearson.

| grupo de parques | parques×réplicas | marcados por BH | tasa | IC95 Clopper–Pearson | ĉ centrado medio | c verdad | SE medio |
|---|---|---|---|---|---|---|---|
| λ = 1.02 (c≈+0.02) | 180 | 180 | 1.000 | [0.980, 1.000] | 0.0238 | 0.0200 | 0.0016 |
| τ = 1.01 (c≈−0.02) | 180 | 180 | 1.000 | [0.980, 1.000] | -0.0237 | -0.0197 | 0.0015 |
| limpios (c=0) | 180 | 4 | 0.022 | [0.006, 0.056] | -0.0001 | 0.0000 | 0.0015 |

**Potencia (contaminados) 1.000** (mínimo 0.8, global y por tipo) · **FPR (limpios) 0.022** (cota 0.0818). Control sin calibración (todos los parques limpios, mismas semillas): 0 de 540 parques marcados, FPR 0.000.

**G2.3a en la sintética (informativo):** pendiente de Deming media 1.419 con calibración por parque contra 1.413 sin ella; la banda [0.85, 1.15] no distingue ambas (D02b).

## Compuertas

- **G2.1** ✅ estudio de simulación sobre δ̃, R = 30 réplicas (semillas 211–240), |sesgo relativo medio| + 1.96·MCSE por nivel < 1 %: Medium -0.146 % + 1.96×0.081 % = 0.305 % ✓ · Extreme -0.188 % + 1.96×0.113 % = 0.410 % ✓ (peor nivel 0.410 %)
- **G2.2** 🔎 (bruto: ❌) 🔎 PROVISIONAL (bruto; Prop. 2″ no pasa la equivalencia). (a) orden estricto ✓: δ̄ No -0.0002 > Medium -0.1014 > Extreme -0.1597 · (b) δ̄ Extreme ∈ [-0.3, -0.15]: ✓ · (c) componente de menor media de la mezcla de Extreme -0.1597 ∈ [-0.32, -0.2]: ✗
- **G2.3a** 🔎 (bruto: ❌) 🔎 PROVISIONAL (bruto; Prop. 2″ no pasa la equivalencia). Deming δ^L sobre δ^D (sobre δ̂ bruto): pendiente 1.556 (EE dos vías 0.018) ∈ [0.85, 1.15] · intercepto -0.0159
- **G2.3b** ✅ detector ê por parque (validación SINTÉTICA del método; LOO + cluster lanzador + Pustejovsky–Tipton + BH 5 %), 30 réplicas × 18 parques: potencia 1.000 (IC95 CP [0.990, 1.000]; λ=1.02: 1.000, 180/180; τ=1.01: 1.000, 180/180; mínimo 0.8) · FPR en parques limpios 0.022 (4/180; IC95 CP [0.006, 0.056]; cota 0.05 + 1.96·√(0.05·0.95/180) = 0.0818). La aplicación a datos reales es 🔎 informativa.
- **G2.4** 🔎 (bruto: ✅) 🔎 PROVISIONAL (bruto; Prop. 2″ no pasa la equivalencia). σ_η = 0.0774 (D) / 0.2810 (L) · SE CR2 mediano de δ̂_g = 0.0089 (límite 0.03; ingenuo 0.0045, efecto de diseño ×1.98) · método CR2 · cobertura del IC95 de δ̃_g (SE delta method con Var(β̂)) en la sintética 0.948 (mínimo 0.9) ✓

Figuras agregadas por juego en `docs/figuras/f2/`: delta_por_cubeta.png, deming_delta_L_vs_D.png, c_g_por_cubeta.png.

### Bloque para el orquestador — F02
- Modelo(s) usado(s): Sonnet (implementación)
- Compuertas: G2.1 ✅ | G2.2 🔎 (bruto: ❌) | G2.3a 🔎 (bruto: ❌) | G2.3b ✅ | G2.4 🔎 (bruto: ✅) — **DETENIDA**: equivalencia de Prop. 2″ no pasa
- Cifras clave: δ̄ᴰ No -0.0002 · Medium -0.1014 ± 0.0022 · Extreme -0.1597 ± 0.0018 · Deming 1.556 · β̂_D -0.148 / β̂_L 0.618 · pendiente predicha 1.897 vs observada 1.556 (equivalencia ✗; IV; adoptado ✗) · σ_η 0.0774 · G2.1 0.410 % (|sesgo|+1.96 MCSE, peor nivel) · cobertura IC95 0.948 · G2.3b potencia 1.00 / FPR 0.022 · 2,112 juegos confirmatorios
- Desviaciones respecto al ROADMAP: Prop. 2″ por 2SLS con RelSpeed (ADR-019, propuesta pendiente de ratificación); G2.3b = validación sintética (LOO + cluster lanzador + Pustejovsky–Tipton, cota de FPR de Morris–White–Crowther); real = 🔎 n/e
- Mejora posible detectada: Prop. 2″ NO adoptada: revisar β̂ y la equivalencia antes de F3; detector ê separable escala/reloj (D02b)
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase02 / (pendiente) / (pendiente)
- Log: reports/logs/f02_<fecha>.log
