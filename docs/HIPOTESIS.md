# Hipótesis pre-registradas (H1–H6) — F1

**Pre-registro.** Este archivo fija las hipótesis **antes** de que cualquier fase con
outcomes corra en local. El timestamp del commit de merge a `main` es la evidencia del
pre-registro (ROADMAP §4-F1). A partir de aquí, Claude Code **no** cambia el estadístico ni la
regla 🟢 de ninguna hipótesis después de ver resultados (CLAUDE.md).

Los estadísticos y las reglas 🟢 están copiados **tal cual** de ROADMAP §4-F1 (v2.7); lo que
este documento añade es la operacionalización exacta: variables del diccionario y de F0, unidad
de análisis, filtros, agrupamiento de errores, tamaño de efecto mínimo relevante (MDE), qué
refuta cada una y qué pruebas entran al único Benjamini–Hochberg.

**Etiquetas de evidencia.** 🟢 confirmada tras BH · 🟡 medida, no sobrevive BH · ⚪ no detectada ·
🔎 exploratoria.

Ninguna hipótesis usa los `*_anon_id` como *feature*: solo para agrupar, validar y agregar
(diccionario `grouping_only`). Stuff+ puro nunca usa ubicación (`PlateLoc*`, `in_strike_zone`,
`EffectiveVelo`, VAA/HAA crudos): CLAUDE.md.

---

## Control de falsos descubrimientos — el único Benjamini–Hochberg (q = 0.10)

ROADMAP §4-F1: **Benjamini–Hochberg con q = 0.10 sobre todas las pruebas confirmatorias
juntas.** Para que el procedimiento sea coherente (BH controla la FDR entre los nulos
**rechazados**), entran a la lista las pruebas cuyo desenlace confirmatorio es un
**descubrimiento** con un valor-p de una cola:

| # en BH | Hipótesis | valor-p que entra | cómo se obtiene |
|---|---|---|---|
| 1 | **H1** | $p$ de $\beta \neq 0$ | de la regresión con errores agrupados por juego |
| 2 | **H2** | ASL bootstrap de una cola de $\Delta^{rel}_{CH}-\Delta^{rel}_{SL\cup CU}>0$ | fracción de réplicas (lanzador) con el contraste $\le 0$ |
| 3 | **H3** | $p$ de una cola del DiD $>0$ | permutación/bootstrap por juego |
| 4 | **H4** | $p$ de Diebold–Mariano (una cola, por juego) | $\Delta\text{LogLoss}>0$ |
| 5 | **H6** | ASL bootstrap de una cola de (fiabilidad Stuff+ − fiabilidad rv) $>0$ | fracción de réplicas con la diferencia $\le 0$ |

**Procedimiento BH ($m = 5$).** Se ordenan los cinco valores-p $p_{(1)}\le\dots\le p_{(5)}$. Sea
$k$ el mayor índice con $p_{(k)}\le \tfrac{k}{5}\,q$ ($q=0.10$). Se rechazan $H_{(1)},\dots,H_{(k)}$.
"Sobrevivir a BH" = ser una de esas rechazadas. El $p_{BH}$ de una hipótesis es su valor-p
ajustado BH; las reglas de §4-F1 que dicen "$p_{BH}<0.10$" se leen como "sobrevive este BH".

**H5 no entra al BH, y es la única excepción.** Su regla 🟢 es de **no rechazo** (invariancia): un
valor-p pequeño en H5 es un **fracaso**, no un descubrimiento. BH controla la FDR entre
rechazos; meter una prueba de equivalencia donde "éxito = no rechazar" invierte el sentido del
procedimiento. H5 se evalúa con su propio criterio pre-registrado (no rechazo a $\alpha=0.10$ del
término de cubeta **y** pendiente de calibración $\in[0.95,1.05]$). Esto no cambia el estadístico
ni la regla 🟢 de H5 (§4-F1): solo declara, como pide §4-F1 punto 1, la lista exacta de pruebas
que entran al BH.

Para H2 y H6 el ASL bootstrap de una cola es el valor-p que las hace comparables en el BH; la
dirección del efecto y el "IC bootstrap sin 0" de §4-F1 se mantienen como condición adicional de
la 🟢 (ver cada hipótesis). No se corrige por multiplicidad ninguna prueba **exploratoria** (🔎):
el BH es solo para las confirmatorias de arriba.

---

## H1 — La densidad escala el movimiento Magnus

- **Afirmación.** La densidad del aire escala el movimiento Magnus.
- **Estadístico (§4-F1, tal cual).** $\beta$ en
  $\log\lVert\mathbf a_\perp\rVert_i=\alpha_{jk}+\beta\log\hat\rho_g+\varepsilon$, con efectos
  fijos lanzador×forma.
- **Regla 🟢 (§4-F1, tal cual).** $p_{BH}<0.10$ y IC95 de $\beta\subset(0.7,1.3)$; la física predice
  $\beta=1$.
- **Variables.** $\mathbf a_\perp$ = componente de la aceleración perpendicular a la velocidad
  (Magnus), construida en F2 desde los 9P (`ax0,ay0,az0,vx0,vy0,vz0`) tras restar la gravedad
  $g$ (§2); $\hat\rho_g$ = densidad por juego estimada en F2 (núcleo del proyecto, ADR-001);
  forma $k$ = clúster de forma de F5 (GMM), con la familia de ADR-002 como respaldo; lanzador
  $j$ = `pitcher_anon_id` (solo agrupa).
- **Unidad de análisis.** El lanzamiento $i$, con efectos fijos por lanzador×forma $\alpha_{jk}$.
- **Filtros.** `excluir_modelo` (exige lanzador válido para el efecto fijo). Fuera la familia
  **EXC** de ADR-002 (Knuckleball/Other/Undefined): casi no giran y la descomposición Magnus no
  aplica. Exige $\hat\rho_g$ de F2.
- **Agrupamiento de errores.** Por **juego**. Razón: el regresor $\log\hat\rho_g$ es constante
  dentro del juego (un solo valor por $g$), así que la información independiente está a nivel de
  juego; errores cluster-robustos por `game_anon_id`.
- **MDE.** La física (Prop. 4, §2) predice $\beta=1$ exacto. El mínimo relevante es que el IC95
  **quepa dentro de $(0.7,1.3)$**: una desviación $>30\%$ respecto a 1 indicaría un canal no-Magnus
  de tamaño físico relevante. Con ~183 mil lanzamientos en *Extreme*, ~294 mil en *No* y 765
  lanzadores en ≥2 cubetas (FASE_00.md), el EE por juego en $\log\hat\rho_g$ (~0.01, §1.1) da
  sobrada potencia para un IC de ese ancho.
- **Qué la refuta.** IC95 de $\beta$ fuera de $(0.7,1.3)$ (p. ej. un canal de arrastre que escale
  distinto), o $\beta$ no distinguible de 0 (no sobrevive BH).
- **BH.** Entra (prueba #1).

## H2 — El cambio gana Stuff+ relativo en altura

- **Afirmación.** El *changeup* gana Stuff+ **relativo** en altura.
- **Estadístico (§4-F1, tal cual).** $\Delta^{rel}_{CH}-\Delta^{rel}_{SL\cup CU}$, con las familias
  de ADR-002 (**CH** incluye Splitter; **SL** incluye Sweeper).
- **Regla 🟢 (§4-F1, tal cual).** Unilateral $>0$, bootstrap por lanzador.
- **Variables.** `familia` de ADR-002: CH = {Changeup, Splitter}; SL∪CU = {Slider, Sweeper,
  Curveball}. Stuff+ de F6. $\Delta^{rel}$ = cambio de Stuff+ de la familia entre alta y baja
  densidad, **relativo** a la media del arsenal del lanzador (resta el nivel del lanzador para
  que el contraste no mida quién lanza en altura, sino cuánto cambia cada familia). Alta/baja por
  la clase de densidad de F2 / cubeta (ADR-005).
- **Unidad de análisis.** Lanzador (el $\Delta^{rel}$ de cada familia se promedia dentro del
  lanzador; el contraste es por lanzador).
- **Filtros.** `excluir_modelo`; lanzadores con muestra suficiente de ambas familias en alta y en
  baja (umbral por celda fijado en F8); EXC fuera.
- **Agrupamiento de errores.** Bootstrap **por lanzador** (se remuestrean lanzadores). Razón: el
  lanzador es la unidad independiente; el efecto ya está promediado dentro de cada uno.
- **MDE.** Mínimo relevante: el contraste positivo equivale a $\ge 0.1$ desviaciones estándar de
  Stuff+ por lanzador; por debajo de eso el "cambio gana en altura" no es accionable para scouting.
  La regla operativa es la de §4-F1 (unilateral $>0$).
- **Qué la refuta.** Contraste $\le 0$ (el cambio no gana más Stuff+ relativo que slider/curva en
  altura), o el IC bootstrap cruza 0 por el lado negativo / no sobrevive BH.
- **BH.** Entra (prueba #2), con el ASL bootstrap de una cola; la dirección $>0$ es condición
  adicional de la 🟢.

## H3 — El rodado vale más en altura

- **Afirmación.** El rodado (ground ball) vale más en altura.
- **Estadístico (§4-F1, tal cual).** DiD:
  $[\bar w_{FB,alta}-\bar w_{FB,baja}]-[\bar w_{GB,alta}-\bar w_{GB,baja}]$ condicionado en EV×LA.
- **Regla 🟢 (§4-F1, tal cual).** $>0$ con $p_{BH}<0.10$.
- **Variables.** $w$ = valor del batazo (pesos lineales de F4). FB/GB = `hit_type` ∈ {FlyBall,
  GroundBall}. EV = `ExitSpeed`, LA = `Angle`; "condicionado en EV×LA" = dentro de celdas de
  velocidad de salida × ángulo, para comparar batazos físicamente equivalentes y aislar el efecto
  de la densidad sobre el *carry*. Alta/baja por densidad (F2) / cubeta (ADR-005).
- **Unidad de análisis.** El batazo (`es_bip`; `evento_terminal` ∈ {1B,2B,3B,HR,OUT_BIP,ROE,SAC}).
- **Filtros.** `excluir_modelo`; `es_bip`; `hit_type`, `ExitSpeed` y `Angle` no nulos.
- **Agrupamiento de errores.** Por **juego**. Razón: la densidad es por juego y el *carry* comparte
  ese shock dentro del juego; errores por `game_anon_id`.
- **MDE.** Mínimo relevante en unidades de $w$ (carreras por batazo): un DiD $\ge 0.01$ run, el
  orden del valor de convertir un out en hit; por debajo no cambia decisiones de arsenal. La regla
  operativa es la de §4-F1 ($>0$).
- **Qué la refuta.** DiD $\le 0$, o no sobrevive BH, o el intervalo de Imbens–Manski no excluye el
  nulo (ver "Datos faltantes").
- **BH.** Entra (prueba #3). **Además** se reporta con intervalo de Imbens–Manski (ver abajo), por
  ser un contraste de outcomes observados entre cubetas.

## H4 — El spin rate solo es insuficiente

- **Afirmación.** El *spin rate* por sí solo no explica el Stuff+.
- **Estadístico (§4-F1, tal cual).** $\Delta\text{LogLoss}$ = (modelo con $\varepsilon,\omega_T$,
  movimiento) − (modelo con *spin rate*), por Diebold–Mariano por juego.
- **Regla 🟢 (§4-F1, tal cual).** Diebold–Mariano por juego, $p_{BH}<0.10$.
- **Variables.** Modelo rico de F6 con densidad $\varepsilon$ (clase/residual de F2), el operador
  de traslación $\omega_T$ (F3) y el movimiento (break/aceleración); modelo base solo con
  `SpinRate`. LogLoss sobre el desenlace del lanzamiento (árbol de ADR-011).
- **Unidad de análisis.** El lanzamiento (predicción); la pérdida se agrega por juego para el DM.
- **Filtros.** `excluir_modelo`; partición de validación de F7 (fuera de muestra), para que el
  $\Delta$ no premie sobreajuste.
- **Agrupamiento de errores.** Por **juego** (el DM se calcula sobre las diferencias de pérdida
  promediadas por juego). Razón: controla la dependencia intra-juego de la pérdida.
- **MDE.** Mínimo relevante: $\Delta\text{LogLoss}>0$ con un tamaño $\ge 10^{-3}$ nats/lanzamiento,
  detectable por DM con ~2 127 juegos. La regla operativa es la de §4-F1.
- **Qué la refuta.** $\Delta\text{LogLoss}\le 0$ (el modelo rico no mejora al de spin rate) o DM no
  significativo tras BH.
- **BH.** Entra (prueba #4).

## H5 — Invariancia de la respuesta del bateador

- **Afirmación.** Dada la forma realizada del lanzamiento, la respuesta del bateador no depende de
  la cubeta (lo que justifica el operador contrafactual, Prop. 7 de F3).
- **Estadístico (§4-F1, tal cual).** LRT del término de cubeta en los nodos N1–N4 dados los rasgos
  realizados.
- **Regla 🟢 (§4-F1, tal cual).** **No** rechazo y pendiente de calibración $\in[0.95,1.05]$.
- **Variables.** N1–N4 = nodos del árbol de desenlace (swing / whiff / contacto / BIP, ADR-011);
  "rasgos realizados" = física del lanzamiento tal como llegó (break, velocidad, ubicación medida),
  no la contrafactual; término de cubeta = `altitude_category` (ADR-005).
- **Unidad de análisis.** El lanzamiento; el LRT compara el modelo de cada nodo con y sin el
  término de cubeta.
- **Filtros.** `excluir_modelo`.
- **Agrupamiento de errores.** Por **lanzador** (la calibración y el LRT se evalúan con pliegues /
  bootstrap por `pitcher_anon_id`, consistentes con la CV agrupada de F7).
- **MDE.** Equivalencia: el término de cubeta no aporta información predictiva más allá de la forma
  realizada y la pendiente de calibración se queda en $[0.95,1.05]$. Una banda de $\pm0.05$ es el
  margen tolerable para que el contrafactual de F3 sea válido.
- **Qué la refuta.** Rechazo del LRT (la cubeta sí aporta a la respuesta dados los rasgos) o
  pendiente de calibración fuera de $[0.95,1.05]$. **Si H5 falla, el contrafactual de F8 cambia de
  diseño: se escala al orquestador** (§4-F1).
- **BH.** **No entra** (prueba de no rechazo / equivalencia; ver "Control de falsos
  descubrimientos").

## H6 — Stuff+ es más fiable que el valor observado

- **Afirmación.** Stuff+ es más fiable (reproducible) que el valor observado del lanzamiento.
- **Estadístico (§4-F1, tal cual).** Split-half de Stuff+ vs. de rv observado, mismo
  lanzador×tipo.
- **Regla 🟢 (§4-F1, tal cual).** Stuff+ mayor, IC bootstrap sin 0.
- **Variables.** Stuff+ de F6; rv observado = valor de carrera del lanzamiento por los pesos
  lineales de F4; fiabilidad = correlación split-half (dos mitades aleatorias del mismo
  lanzador×tipo), con corrección Spearman–Brown. Tipo = `AutoPitchType` crudo o forma de F5
  (se fija el nivel en F6).
- **Unidad de análisis.** Lanzador×tipo.
- **Filtros.** `excluir_modelo`; lanzador×tipo con muestra mínima por mitad (umbral fijado en F6).
- **Agrupamiento de errores.** Bootstrap por **lanzador×tipo** (unidad del split-half), anidado en
  lanzador.
- **MDE.** Mínimo relevante: la fiabilidad de Stuff+ supera a la del rv observado con el IC
  bootstrap de la diferencia sin 0; una ventaja $\ge 0.05$ en correlación es relevante para preferir
  Stuff+ como métrica de scouting.
- **Qué la refuta.** Fiabilidad de Stuff+ $\le$ la del rv observado, o el IC bootstrap de la
  diferencia incluye 0 / no sobrevive BH.
- **BH.** Entra (prueba #5), con el ASL bootstrap de una cola; el "IC bootstrap sin 0" de §4-F1 es
  condición adicional de la 🟢.

---

## Datos faltantes (ADR-016)

De F0 (§1.5): **mecanismo U** (outs no contabilizados: dobles matanzas registradas como 1 out, no
turnos perdidos) con `qa.mecanismo_outs = U`, y **`qa.perdida_ignorable = false`** porque
$W(\Gamma{=}2)/\mathrm{SE}_{ref}=3.55$.

Que el mecanismo sea U importa para el pre-registro: **U no quita lanzamientos**, así que la física
por lanzamiento (H1), el LogLoss (H4), la fiabilidad (H6) y las formas (H2) no sufren sesgo de
selección por este mecanismo. Lo que sí queda tocado son los **contrastes de outcomes observados
entre cubetas**, porque `perdida_ignorable = false`: el componente residual L y la práctica de
registro por cubeta (🔎 gradiente de P de §1.5) pueden sesgar una comparación entre cubetas.

**Regla pre-registrada (§4-F1 punto 2).** Toda prueba que compare outcomes observados entre cubetas
—**H3** y la corroboración de F8— se reporta **también** con el intervalo de Imbens–Manski usando las
cotas de la Prop. 17 (ancho del conjunto identificado del contraste Extreme − No,
$W(\Gamma)=\sum_{b\in\{Ext,No\}}\Gamma\hat r_b/(\tilde m_b+\Gamma\hat r_b)$, con $\Gamma=2$). Entonces:

- 🟢 exige **sobrevivir BH** y **además** que el intervalo de Imbens–Manski **excluya el nulo**.
- Si pasa BH pero el intervalo IM **no** excluye el nulo → **🟡** (medida, pero la incertidumbre de
  identificación la deja sin confirmar).

H1, H2, H4, H5 y H6 no son contrastes de outcomes observados entre cubetas (son física por
lanzamiento, formas, LogLoss, equivalencia o fiabilidad), así que no llevan intervalo IM; su 🟢 es
la de §4-F1 más el BH.

---

## Lo visto antes del pre-registro

Para transparencia (§4-F1 punto 3): estas cifras por cubeta de `reports/FASE_00.md` ya se vieron
antes de fijar H1–H6. **Ninguna es estadístico de H1–H6** — son control de calidad de datos
(ADR-002 a 016), no outcomes de las hipótesis.

**Alcance** (FASE_00.md): 635 002 lanzamientos · 2 127 juegos · 1 134 lanzadores · 864 bateadores ·
2024–2026. 765 lanzadores con ≥30 lanzamientos en ≥2 cubetas (identificación intra-lanzador). Por
cubeta (sumando los tres años):

| cubeta | juegos | lanzamientos |
|---|---|---|
| Extreme Altitude | 604 | 183,267 |
| Medium Altitude | 509 | 154,840 |
| No Altitude | 1,004 | 293,875 |
| (sin cubeta) | 10 | 3,020 |

**$f_b$ = % de medias entradas de T sin corredores ($Z$)** (Prop. 16, FASE_00.md): Extreme 24.90 %,
Medium 26.38 %, No 31.77 % (global 28.50 %).

**Tasa de $P$ (2 outs registrados en T)**: Extreme 14.81 %, Medium 12.30 %, No 10.35 % (global
12.09 %). La tasa de "out faltante por cubeta" (antiguo G0.8, informativa): 14.27 / 11.71 / 9.87 %.

**OR del logit de $1[h\in P]$ vs. No Altitude** (corroboración c, FASE_00.md): Extreme
1.510 [1.39, 1.63], Medium 1.211 [1.11, 1.32]; al controlar por $N_h$: 1.426 [1.31, 1.55] y
1.146 [1.05, 1.25].

Estas cantidades describen el **mecanismo de los outs faltantes** (ADR-016, mecanismo U) y el
alcance del dataset. El valor de un batazo (H3), el Stuff+ (H2, H6), el movimiento Magnus (H1), el
LogLoss (H4) y la respuesta del bateador (H5) **no** se han calculado ni mirado: F2–F6 aún no han
corrido.
