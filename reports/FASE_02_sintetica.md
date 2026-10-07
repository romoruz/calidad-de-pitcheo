# FASE 02 — etapa sintética (estudio de simulación de G2.1, G2.3b y cobertura de G2.4)

n_jobs 3 · caché sí · hash de código b117525b18cbe8c2 · 388.4s ({'g21': 107.7, 'staff': 1.6, 'g23b': 279.1})

## Sintética con física exacta: estudio de simulación de G2.1 (ADR-017/019)

`solve_ivp` DOP853 (rtol 1e-10), ρ conocida en 3 niveles (1.00, 0.82, 0.76·ρ₀), **C_D = C_D(Re) con ley potencial pura (pendiente local en log Re = β_D = -0.3, sin ningún otro término en v; ADR-019 D1)**, C_L(S) sin Re (β_L = 0.0), ruido de posición, 9P de aceleración constante por mínimos cuadrados, efecto de lanzador α_j (SD 0.05 en log C_D) con planteles asignados a parques locales. **Protocolo pre-registrado** (Morris, White y Crowther 2019): R = 30 réplicas independientes, semillas 241–270 (**las semillas 101–110 y 201–210 están consumidas**: D02b §4 y D02c §8), 150 juegos × ≈250 lanzamientos (≈37,522 por réplica), estimando log(ρ_nivel/ρ_No). Aprueba si, por nivel, |sesgo relativo medio| + 1.96·MCSE < 1 %. Réplicas leídas de la caché: 0 de 30.

**Primario de G2.1 (δ̂)**: δ̂ bruto (Prop. 2″ no activa o β no estimable).

| nivel | sesgo relativo medio | MCSE | |sesgo| + 1.96·MCSE | veredicto | SE empírico δ̂ | RMSE δ̂ | cobertura IC95 | juegos×réplicas |
|---|---|---|---|---|---|---|---|---|
| Medium Altitude | -0.034 % | 0.120 % | 0.268 % | ✓ | 0.0230 | 0.0230 | 0.813 | 1072 |
| Extreme Altitude | +0.128 % | 0.120 % | 0.362 % | ✓ | 0.0238 | 0.0238 | 0.814 | 1329 |

**β̂ en el estudio** (R = 30, estimador IV): β̂_D = -0.305 ± 0.020 (SE medio 0.020; verdad -0.3), β̂_L = -0.022 ± 0.032 (verdad 0.0). MCO sin instrumento: β̂_D = -0.562 (sesgo por endogeneidad de log‖v̄‖, ADR-019). R² de colinealidad log‖v̄‖ medio = 0.960.

**Equivalencia de pendientes (informativa, no es compuerta en la sintética):** predicha (1+β̂_L)/(1+β̂_D) = 1.409 contra Deming observada 1.415; aprueban ±0.1: 0 de 30 réplicas.

**Cobertura del IC95 de δ̂_g (SE delta method con Var(β̂) si primario δ̃) sobre todos los juegos × réplicas (4,500): 0.856** ⚠ **ALERTA: cobertura < 0.90, el SE subestima**. σ_η medio (bruto) 0.0496. Errores por réplica (Medium / Extreme): -0.11 % / +0.59 %; +0.45 % / +0.23 %; +0.45 % / +0.40 %; -1.42 % / -1.89 %; -1.05 % / -0.15 %; -0.09 % / +0.00 %; -0.69 % / -0.41 %; -0.72 % / +0.04 %; -0.63 % / +0.33 %; +1.31 % / +0.93 %; +1.19 % / +0.83 %; -0.40 % / -0.30 %; -0.05 % / -0.30 %; -0.57 % / -0.52 %; +0.75 % / +1.09 %; +0.14 % / -0.09 %; -0.58 % / -0.67 %; +0.59 % / +0.45 %; +0.50 % / -0.38 %; +0.29 % / -0.03 %; +0.05 % / +0.56 %; +0.64 % / +0.50 %; -0.28 % / +0.08 %; -0.67 % / +0.19 %; +0.77 % / +0.74 %; -0.28 % / +0.89 %; -0.27 % / +0.82 %; -0.48 % / +0.72 %; -0.36 % / -1.14 %; +0.50 % / +0.29 %.

**Planteles locales** (semilla 241): RMSE de δ̂ contra su estimando (1+β_D)·log ρ 0.0205 sin α_{j,k} → 0.0109 con α_{j,k} (Prop. 2′): el segundo efecto fijo elimina el sesgo del C_D medio del plantel.

## Sintética de calibración para G2.3b (ADR-018/019, F2.5b)

18 parques (6 por cubeta); en cada cubeta λ = 1.02 en 2 parques, τ = 1.01 en otros 2 y 2 limpios (c = λ/τ² − 1 ≈ ±0.02). 300 juegos × ≈250 lanzamientos por réplica, R = 30 (semillas 241–270). Detector ê con id de parque: contraste LOO (c_p − media del resto de la cubeta), cluster = lanzador, t de Pustejovsky y Tipton (2018) y BH al 5 %. Criterio (ADR-019 D3): potencia ≥ 0.8 y FPR ≤ 0.05 + 1.96·√(0.05·0.95/n_limpios) = 0.0818 (n_limpios = 180; Morris, White y Crowther 2019 §5.2), con IC de Clopper–Pearson.

| grupo de parques | parques×réplicas | marcados por BH | tasa | IC95 Clopper–Pearson | ĉ centrado medio | c verdad | SE medio |
|---|---|---|---|---|---|---|---|
| λ = 1.02 (c≈+0.02) | 180 | 180 | 1.000 | [0.980, 1.000] | 0.0240 | 0.0200 | 0.0015 |
| τ = 1.01 (c≈−0.02) | 180 | 180 | 1.000 | [0.980, 1.000] | -0.0237 | -0.0197 | 0.0016 |
| limpios (c=0) | 180 | 7 | 0.039 | [0.016, 0.078] | -0.0003 | 0.0000 | 0.0016 |

**Potencia (contaminados) 1.000** (mínimo 0.8, global y por tipo) · **FPR (limpios) 0.039** (cota 0.0818). Control sin calibración (todos los parques limpios, mismas semillas): 4 de 540 parques marcados, FPR 0.007.

**G2.3a histórica en la sintética (informativo, ADR-017):** pendiente de Deming media 1.418 con calibración por parque contra 1.413 sin ella; la banda [0.85, 1.15] no distingue ambas (D02b). Reemplazada por G2.3a de ADR-020 (consistencia física del canal D).

### 🔎 Informativo (ADR-020): sesgo por parque de δᴸ inducido por c_g contra la predicción κ̄·c

Prop. 3′ predice que el residuo de calibración c_g·g desplaza δᴸ en κ̄·c (κ̄ = -1.044; n = 540 parques × réplicas con calibración). Promedios y correlación observados:

| tipo | n | sesgo medio δᴸ por parque | κ̄·c medio |
|---|---|---|---|
| lambda | 180 | -0.1631 | -0.0209 |
| tau | 180 | -0.1570 | 0.0206 |
| limpio | 180 | -0.1530 | 0.0000 |

Correlación entre el sesgo de δᴸ por parque y κ̄·c = **0.021**. No es compuerta; solo informa que el canal L lleva el residuo c_g·g con la magnitud que predice Prop. 3′.

## Compuertas sintéticas

- **G2.1** ✅ estudio de simulación sobre δ̂, R = 30 réplicas (semillas 241–270), |sesgo relativo medio| + 1.96·MCSE por nivel < 1 %: Medium -0.034 % + 1.96×0.120 % = 0.268 % ✓ · Extreme +0.128 % + 1.96×0.120 % = 0.362 % ✓ (peor nivel 0.362 %)
- **G2.3b** ✅ detector ê por parque (validación SINTÉTICA del método; LOO + cluster lanzador + Pustejovsky–Tipton + BH 5 %), 30 réplicas × 18 parques: potencia 1.000 (IC95 CP [0.990, 1.000]; λ=1.02: 1.000, 180/180; τ=1.01: 1.000, 180/180; mínimo 0.8) · FPR en parques limpios 0.039 (7/180; IC95 CP [0.016, 0.078]; cota 0.05 + 1.96·√(0.05·0.95/180) = 0.0818). La aplicación a datos reales es 🔎 informativa.
- **G2.4_cobertura** ❌ cobertura del IC95 de δ̂_g (SE delta method con Var(β̂)) en la sintética 0.856 (mínimo 0.9)
