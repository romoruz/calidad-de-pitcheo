# FASE 02 — etapa sintética (estudio de simulación de G2.1, G2.3b y cobertura de G2.4)

n_jobs 3 · caché sí · hash de código b117525b18cbe8c2 · 225.0s ({'g21': 49.5, 'staff': 2.0, 'g23b': 173.5})

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

## Compuertas sintéticas

- **G2.1** ✅ estudio de simulación sobre δ̃, R = 30 réplicas (semillas 211–240), |sesgo relativo medio| + 1.96·MCSE por nivel < 1 %: Medium -0.146 % + 1.96×0.081 % = 0.305 % ✓ · Extreme -0.188 % + 1.96×0.113 % = 0.410 % ✓ (peor nivel 0.410 %)
- **G2.3b** ✅ detector ê por parque (validación SINTÉTICA del método; LOO + cluster lanzador + Pustejovsky–Tipton + BH 5 %), 30 réplicas × 18 parques: potencia 1.000 (IC95 CP [0.990, 1.000]; λ=1.02: 1.000, 180/180; τ=1.01: 1.000, 180/180; mínimo 0.8) · FPR en parques limpios 0.022 (4/180; IC95 CP [0.006, 0.056]; cota 0.05 + 1.96·√(0.05·0.95/180) = 0.0818). La aplicación a datos reales es 🔎 informativa.
- **G2.4_cobertura** ✅ cobertura del IC95 de δ̃_g (SE delta method con Var(β̂)) en la sintética 0.948 (mínimo 0.9)
