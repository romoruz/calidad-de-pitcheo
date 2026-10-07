# Decisiones de arquitectura (ADR)

Registro de ADRs del proyecto (ROADMAP §5). Plantilla: contexto, decisión, alternativas,
consecuencias. El **ADR-001** ("ρ por juego desde la trayectoria porque el dataset no trae
estadio ni clima") lo escribe F1; los ADR que el roadmap pedía en F4 y F6 pasan a ser 008 y 009.

Los ADR-002 a 007 son **decisiones del orquestador** (ROADMAP v2.3 §1.1) sobre los hallazgos de
`docs/discrepancias/D00.md`. Ninguna usa outcomes: son inventarios de etiquetas y reglas de
limpieza, y F1 (pre-registro) aún no ocurre, así que fijarlas ahora no es post hoc. Las
implementa F0 en `src/pitcheo/limpieza.py`; las categorías reales y sus mapas viven en
`config/categorias.yaml` (`docs/diccionario.csv` es del organizador y no se edita). Un valor sin
regla nunca se asigna en silencio: hace fallar la fase (G0.5).

---

## Plantilla de ADR

Cada decisión de arquitectura se registra con cuatro apartados (ROADMAP §5):

- **Contexto.** El problema o hallazgo y por qué hay que decidir ahora.
- **Decisión.** Lo que se hace, en términos operativos.
- **Alternativas.** Qué más se consideró y por qué se descartó.
- **Consecuencias.** Qué cambia en el resto del roadmap (fases, compuertas, código) y qué riesgo
  queda abierto.

Los ADR posteriores (002 en adelante) ya siguen esta estructura aunque la expresen en prosa o en
tabla.

---

## ADR-001 — ρ por juego desde la trayectoria, porque el dataset no trae estadio ni clima

- **Contexto.** El efecto altitud del reto depende de la densidad del aire ρ de cada lanzamiento.
  El diccionario del organizador **no** trae estadio, fecha ni clima: solo `altitude_category`
  (tres cubetas) y `year` (ROADMAP §1, hallazgo 2). No se puede unir con una fuente externa de
  clima (Open-Meteo) ni hacer un *park holdout* real, porque no hay identificador de parque ni de
  partido con fecha. Lo que sí hay es la cinemática 9P completa (`x0…az0`) y los polinomios de
  trayectoria, que son exactos (ADR-010, enmienda): la trayectoria contiene la huella de ρ a
  través del arrastre y del Magnus.
- **Decisión.** Estimar la densidad **por juego** $\hat\rho_g$ directamente desde la propia
  trayectoria (F2), y no desde una tabla de altitudes. La cubeta `altitude_category` se usa solo
  para imputación por juego (ADR-005) y para reportes; "Harp Helú" se define por **densidad**
  (la moda de la clase de densidad más alta dentro de *Extreme*), no por el nombre del estadio.
  Es el núcleo del proyecto (ROADMAP §1, hallazgo 1).
- **Alternativas.** (a) Usar la altitud nominal de la cubeta como ρ: la cubeta *Extreme* mezcla
  parques sobre ~1 800 m con densidades distintas (ADR-005), y colapsarlos pierde la variación que
  mueve el lanzamiento. (b) Unir con clima externo: imposible sin estadio ni fecha. (c) Tratar la
  cubeta como efecto fijo sin ρ continua: no permite H1 (que necesita $\log\hat\rho_g$ continuo) ni
  el operador de traslación de F3.
- **Consecuencias.** F2 estima $\hat\rho_g$ con un EE por juego de ~0.01 en $\log\rho$ (§1.1), lo
  que da potencia a H1. Las columnas que dependen de ρ (`ZoneSpeed`, `SpeedDrop`, `*Break`, `pfx*`)
  son los **canales** del efecto y se transforman con el operador $T$ en el contrafactual (F3,
  hallazgo 6). La cubeta nula de 10 juegos (3 020 lanzamientos) queda fuera de las pruebas
  confirmatorias y F2 le **predice** la cubeta como validación 🔎 (ADR-005). Riesgo abierto: si la
  trayectoria no identifica ρ con suficiente precisión por juego, H1 pierde potencia; se mide en la
  compuerta de F2.

---

## ADR-002 — `AutoPitchType` (12 valores): se conserva la etiqueta y se agrega `familia`

- **Contexto.** El dato real trae 12 valores; el diccionario lista 8 (extra: `Knuckleball`,
  `OneSeamFastBall`, `Sweeper`, `TwoSeamFastBall`). ROADMAP §1.1.
- **Decisión.** La etiqueta cruda se conserva en `AutoPitchType` y se agrega `familia`:
  **FF** = Four-Seam · **SI** = Sinker, TwoSeamFastBall, OneSeamFastBall · **FC** = Cutter ·
  **SL** = Slider, Sweeper (con bandera `es_sweeper`) · **CU** = Curveball · **CH** = Changeup,
  Splitter · **EXC** = Knuckleball, Other, Undefined. `EXC` se excluye de modelos
  (`excluir_modelo`, motivo `ADR-002:EXC`).
- **Alternativas.** Colapsar todo a los 8 del diccionario (pierde Sweeper); dejar Splitter como forma
  propia (rompe H2); modelar el knuckleball (la física de F2 no aplica).
- **Consecuencias.** Two-seam y one-seam son la misma familia física que el sinker. Sweeper es un
  slider de quiebre horizontal. Splitter y changeup engañan por diferencial de velocidad, que es el
  mecanismo de H2. El knuckleball casi no gira: la descomposición Magnus de F2 no aplica. Las formas
  de F5 (GMM) siguen siendo la representación principal; la familia solo se usa para la recta
  primaria, H2 y reportes.

## ADR-003 — Mano `Undefined` / `Switch`

- **Contexto.** `PitcherThrows` trae `Undefined` (y nulos); `BatterSide` trae `Switch` y
  `Undefined` (y nulos). El diccionario solo dice Right/Left. El espejo de zurdos (F5.1) y el
  pelotón necesitan mano resuelta en cada lanzamiento. ROADMAP §1.1.
- **Decisión.** Columnas `pitcher_throws_r` y `batter_side_r` (booleanas: `True` = derecho; nulo =
  descartado, motivos `ADR-003:lanzador` y `ADR-003:bateador`). Un nulo se trata como `Undefined`.
  - **Lanzador:** moda del lanzador si su participación ≥ 95 %; si no, signo de `RelSide`, solo si
    en las filas con mano definida el signo concuerda con la mano ≥ 99 % (el signo se **aprende** de
    los datos: se elige la orientación con mayor concordancia, no se supone); si no, descartar.
  - **Bateador:** `Switch` → mano opuesta a la del lanzador; `Undefined` → moda del bateador si
    ≥ 95 %; si el bateador muestra ambos lados ≥ 5 % cada uno, opuesta al lanzador; si no, descartar.
- **Alternativas.** Descartar todo lo indefinido (pierde filas); suponer el signo de `RelSide`
  (fabrica mano en datos que podrían tener otra convención).
- **Consecuencias.** Un ambidiestro batea casi siempre del lado contrario al lanzador. Las
  participaciones del bateador se calculan después de resolver los `Switch`. Un bateador o lanzador
  sin identificador (nulo) no tiene moda: solo le queda el signo de `RelSide` (lanzador) o se descarta
  (bateador). El reporte cuenta cada vía (moda, signo, descartada).

## ADR-004 — `PitchCall`: los tres fouls se unifican

- **Contexto.** `FoulBall` viene dividido en `FoulBallFieldable` y `FoulBallNotFieldable`, y hay
  `PitchCall = Undefined`. ROADMAP §1.1.
- **Decisión.** `FoulBall`, `FoulBallFieldable`, `FoulBallNotFieldable` → **`Foul`** en la columna
  `pitch_call_h` (la cruda se conserva). `Undefined` se excluye de modelos y de la estimación de la
  cadena de conteos (`ADR-004:Undefined`). **I6 se reescribe (I6′):** `is_swing = is_whiff +
  is_contact` e `is_contact ⇔ pitch_call_h ∈ {Foul, InPlay}`.
- **Alternativas.** Mantener los tres fouls separados (la cadena y N3 no los distinguen); imputar el
  `Undefined`.
- **Consecuencias.** Para la cadena y para N3 los tres son el mismo evento: foul sin out. Un foul
  atrapado es out y Trackman lo marca `InPlay`.

## ADR-005 — `altitude_category` y "Harp Helú"

- **Contexto.** `altitude_category` es nula en una pequeña fracción de filas. Con 2 127 juegos en 3
  temporadas el dataset es de **toda la liga**, no solo de Diablos (que juega ~45 en casa por
  temporada), y la cubeta *Extreme* mezcla varios parques sobre ~1 800 m. ROADMAP §1.1.
- **Decisión.** (a) **Nulos:** si la cubeta es constante dentro de cada juego (identidad **I9**), se
  imputa por juego en `altitude_category_h`; si el juego entero es nulo, queda sin cubeta, fuera de
  las pruebas confirmatorias, y F2 le **predice** la cubeta desde ρ̂_g como validación 🔎.
  (b) **Composición:** toda la liga. (c) **Definición operativa:** "Stuff+ en Harp Helú" = Stuff+
  evaluado en ρ_CDMX, la moda de la clase de densidad más alta que F2 encuentre dentro de *Extreme*.
  La cubeta *No Altitude* es la referencia y las cubetas no traen altitud numérica (G2.2 pide orden y
  rangos de densidad, no una pendiente contra metros).
- **Alternativas.** Descartar los juegos con cubeta nula; asumir que *Extreme* = CDMX.
- **Consecuencias.** CDMX (2 232 m, ρ/ρ₀ = 0.762) y Puebla (2 192 m, 0.766) tienen el mismo aire:
  ningún método físico los separa, y para la pregunta del reto da igual, porque lo que mueve el
  lanzamiento es ρ, no el nombre del estadio. Aguascalientes, Durango y León (~0.79–0.80) sí son
  separables con un error estándar por juego de ~0.01 en log ρ. La hipótesis "solo Diablos" queda
  descartada por el número de juegos.

## ADR-006 — `Outs = 3`

- **Contexto.** 8 filas con `Outs = 3` (diccionario: 0–2). ROADMAP §1.1.
- **Decisión.** Se excluyen de modelos y de la cadena (`ADR-006:Outs`); se conservan para la suma de
  I7. Identidad nueva **I10**: `Outs ∈ {0,1,2}` (se reporta el conteo de violaciones).
- **Alternativas.** Corregirlas a 2 (inventa un valor); borrarlas (rompe la suma de I7).
- **Consecuencias.** Son errores de captura; 8 de 635 002 no mueven nada, pero quedan contadas.

## ADR-007 — `play_result`: evento terminal por prioridad

- **Contexto.** `play_result` tiene 16 valores y mezcla resultados de turno con valores de
  lanzamiento (`BallCalled`, `StrikeSwinging`, `FoulBallFieldable`, `NeutralPlay`…). ROADMAP §1.1.
- **Decisión.** Columna `evento_terminal` (nula = no terminal), por prioridad:
  1. `KorBB = Strikeout` → **K**; `KorBB = Walk` → **BB**.
  2. `pitch_call_h = HitByPitch` → **HBP** (en el dato real `is_hit_by_pitch` es siempre 0).
  3. `InPlay` + `play_result` ∈ Single/Double/Triple/HomeRun → **1B/2B/3B/HR**; Out o
     FieldersChoice → **OUT_BIP**; Error → **ROE**; Sacrifice → **SAC**.

  Cualquier otro valor inventariado → no terminal. Todo valor **sin regla** (no inventariado en
  `config/categorias.yaml`) → discrepancia: la fase falla y lo lista, no se adivina.
- **Alternativas.** Usar solo `play_result` (confunde lanzamiento y turno); fundir ROE y SAC en
  OUT_BIP.
- **Consecuencias.** En la regresión de pesos lineales (F4.1), ROE y SAC llevan su propio peso porque
  sí generan carreras; omitirlos sesgaría a los demás. Para valorar al **lanzador** (N5) un error
  cuenta como out: es responsabilidad de la defensa. El reporte de F0 trae la tabla
  `play_result × pitch_call_h × KorBB` con el evento asignado y una lista de incoherencias (que se
  reportan, no fallan) para que el orquestador revise cualquier combinación inesperada.

---

# Decisiones sobre la corrida real de F0 (ROADMAP v2.4 §1.2)

En la corrida local de F0 fallaron G0.1, G0.2 y G0.3. Ninguna falla fue un error de código: las tres
eran supuestos del roadmap que el dato real no cumple. Son reglas de **control de calidad de datos**,
no hipótesis, y F1 (pre-registro) aún no ocurre; por eso se redefinen con su justificación, sin sesgo
post hoc. Las compuertas v2.4 están en ROADMAP §4-F0. (Los ADR-008 y 009 quedan reservados para F4 y F6.)

## ADR-010 — Ejes de los polinomios de trayectoria: la trayectoria canónica es la de los 9P

- **Contexto.** I3 (`2·c2 = a0`) dio 0 %: las razones 2·c2/a0 medianas fueron X −1.87, Y −1.00, Z 0.17.
  Y da −1.00 casi exacto (el eje Y del polinomio corre en sentido opuesto al `y` de los 9P); X y Z no dan
  ±1, así que **los ejes del polinomio no son los de los 9P**. No es un problema de origen de tiempo: un
  desplazamiento de tiempo no cambia `c2`. ROADMAP §1.2.
- **Decisión.** La trayectoria canónica es la de los 9P: `r(t) = r0 + v0·t + ½·a·t²`
  (`fisica.trayectoria_9p`), el mismo modelo de aceleración constante con convención ya conocida. F0
  identifica el mapeo con una **matriz 3×3** de regresiones (`c2` sobre `ax0/ay0/az0`, `c1` sobre
  `vx0/vy0/vz0` y, informativo, `c0` sobre `x0/y0/z0`; pendiente, intercepto y R²) y busca la permutación
  con signo de mayor R² mínimo. Si alcanza R² ≥ 0.99 en los tres ejes se documenta y los polinomios sirven
  de verificación cruzada; si no, se declaran **no canónicos** y no se usan. Si `c1` encaja con un desfase,
  se estima `t_s = (s·c1 − v0)/a0`. Como diagnóstico extra se reporta una regresión conjunta (cada eje del
  polinomio sobre los tres de los 9P), que detecta un marco **rotado** que ninguna permutación explica.
- **Alternativas.** Corregir el signo de Y y seguir con los polinomios (deja X y Z sin explicar); usar los
  polinomios como canónicos (convención desconocida).
- **Consecuencias.** Ninguna fase depende de los polinomios. G0.2 pasa si se produce la matriz y hay
  decisión; en ambos casos pasa porque la trayectoria canónica es 9P. `fisica.verificar_9p` contrasta los 9P
  con el propio dato: la posición en t = ZoneTime debe reproducir PlateLocSide/PlateLocHeight y `y(ZoneTime)`
  debe caer en el frente del plato (17/12 ft).

## ADR-011 — El árbol de desenlaces se define desde `pitch_call_h`

- **Contexto.** I6′ dio 99.75 % (suma 99.93 %; contacto ⇔ Foul/InPlay 99.75 %; whiff ⇒ StrikeSwinging
  100 %). Las banderas `is_*` del organizador no son partición exacta de `PitchCall` en ~0.25 % de los
  lanzamientos (probablemente foul tips y fouls atrapables marcados distinto), e `is_hit_by_pitch` es
  siempre 0. ROADMAP §1.2.
- **Decisión.** El árbol se define desde `pitch_call_h` (columnas `es_swing`, `es_whiff`, `es_contacto`,
  `es_foul`, `es_bip`): swing = {StrikeSwinging, Foul, InPlay}; whiff = StrikeSwinging; contacto = {Foul,
  InPlay}; las filas `Undefined` quedan en nulo. Es una partición exacta por construcción. Las `is_*` quedan
  como verificación cruzada con su tabla de discrepancias (cada combinación derivada × bandera × `pitch_call_h`
  con su n). En el conteo manda `evento_terminal` (ADR-007) sobre `pitch_call_h`: un foul con `KorBB =
  Strikeout` es K.
- **Alternativas.** Arreglar las banderas a mano (no hay regla verificable); descartar las filas discrepantes.
- **Consecuencias.** G0.1 exige I6′ ≥ 99.5 % **y** la tabla de discrepancias; I1 e I2 siguen en 99.9 %.

## ADR-012 — Completitud de media entrada: criterios A y B

- **Contexto.** I7 dio 86.1 %: de 37 023 medias entradas, 31 883 suman 3 outs, **4 763 suman 2**, 276 suman
  0-1 y 101 suman ≥ 4. La última media entrada del juego explica apenas 0.5 pp. Candidatos: un tercer out en
  un evento sin lanzamiento propio (robo, pickoff), lanzamientos faltantes de Trackman, o `OutsOnPlay` que no
  cuenta ciertos outs. ROADMAP §1.2.
- **Decisión.** Dos criterios por media entrada (`media_entrada_A`, `media_entrada_B`):
  **A (estricto):** suma de `OutsOnPlay` = 3. **B (amplio):** hay estado previo `Outs = 2` en la media entrada
  y existe una media entrada posterior del juego (no es la final). Las de ≥ 4 outs son inconsistentes y se
  excluyen de ambos. F4.1 usa **A** como principal y **B** como sensibilidad; si los pesos difieren más que sus
  IC, se escala al orquestador. F0 produce el diagnóstico de las de 2 outs: % que es la última del juego,
  `OutsOnPlay × evento_terminal` (¿cuenta el out de los ponches?), lanzamientos por media entrada contra las de
  3 outs, outs implicados por los eventos terminales contra `OutsOnPlay`, y los **turnos incompletos**
  (bateadores de la media entrada sin evento terminal: sin orden de lanzamientos es la forma reconstruible del
  "último turno").
- **Alternativas.** Descartar toda media entrada que no sume 3 (pierde 13 % de los datos); asumir sin
  diagnóstico que el tercer out falta.
- **Consecuencias.** G0.3 exige el criterio B ≥ 95 % de las medias entradas **no finales** y el diagnóstico
  producido. "No final" = existe una media entrada posterior del mismo juego en el dato.

## ADR-013 — IDs nulos: dos banderas de exclusión

- **Contexto.** `pitcher_anon_id` es nulo en 3 272 lanzamientos (0.52 %), `batter_anon_id` en 2 020 y
  `catcher_anon_id` en 2 325. Un ID nulo de lanzador formaría un "lanzador fantasma" en `GroupKFold` y en los
  rasgos de arsenal. ROADMAP §1.2.
- **Decisión.** Dos banderas separadas, cada una con su motivo. **`excluir_modelo`** (`motivo_exclusion`): lo de
  ADR-002/003/004/006 **más** `pitcher_anon_id` nulo (`ADR-013:pitcher_id_nulo`). **`excluir_cadena`**
  (`motivo_cadena`): solo `pitch_call_h = Undefined`, `Outs` inválido y `play_result = NeutralPlay` con
  `InPlay` (bola en juego sin resultado, 7 filas). La cadena de conteos y los pesos lineales usan **todas** las
  transiciones válidas, porque la mano o el ID no afectan a la transición del conteo.
- **Alternativas.** Una sola bandera (saca del conteo filas válidas); imputar el ID.
- **Consecuencias.** G0.6 exige `excluir_modelo` ≤ 3 % y `excluir_cadena` ≤ 0.5 %. Con la corrida real:
  exclusiones de modelo ≈ 0.85 % y de cadena ≈ 0.14 %.

---

# Decisiones sobre la segunda corrida de F0 (ROADMAP v2.5 §1.3)

La segunda corrida confirmó que los polinomios sí son los 9P (la regla de v2.4 estaba mal), expuso un error de reloj en la
verificación de la trayectoria y mostró que los outs que faltan son turnos finales perdidos, no robos. Siguen siendo reglas
de **control de calidad de datos**, no hipótesis; F1 aún no ocurre.

## ADR-010 (enmienda) — Los polinomios son los 9P en ejes permutados, con el origen de tiempo en la liberación

- **Contexto.** La regresión conjunta de `c2` dio R² = 1.000000 con coeficientes exactamente 0.5: `c2^X = ½ay0`,
  `c2^Y = ½az0`, `c2^Z = ½ax0`, una **permutación exacta** (X→y, Y→z, Z→x, signos +). v2.4 la rechazó porque comparó `c1`
  con `v0` sin tiempo; si el polinomio empieza en `t_s`, entonces `c1 = v0 + a·t_s` y
  `c0 = r0 + v0·t_s + ½·a·t_s²`, y `c1` ya no encaja con `v0` solo. El eje con más curvatura (el vertical) pierde más R²
  (0.989), justo lo observado. ROADMAP §1.3.
- **Decisión.** La permutación se elige con `c2`, que **no depende del origen de tiempo**. `t_s` por lanzamiento =
  `(s·c1_X − v0)/a0` con el eje de los 9P al que corresponde el eje X del polinomio (con la permutación real,
  `(c1_X − vy0)/ay0`), con su distribución (mediana, IQR, p1, p99). Se regresa `c1` de cada eje sobre `(v0 + a0·t_s)` del eje
  permutado (R² y pendiente); el eje de referencia sale 1 por construcción y los otros dos son la prueba independiente. Los
  polinomios se reclasifican de `no_canonicos` a **`equivalentes`** si `c2` (por pares y conjunta) tiene R² ≥ 0.9999 y `c1`
  con `t_s` R² ≥ 0.999 en los tres ejes (G0.2). La trayectoria canónica sigue siendo la de los 9P.
- **Alternativas.** Mantener los polinomios como no canónicos (descarta una verificación cruzada gratis y deja sin explicar
  `t_s`); elegir la permutación con `c1` también (lo que falló en v2.4).
- **Consecuencias.** El polinomio da `t_s` por lanzamiento, que es el desfase entre los dos relojes (ADR-014). Con el
  intercepto del eje X, `t_s ≈ −0.026 s`: el polinomio arranca en la liberación (~54 ft).

## ADR-014 — Marco temporal único de los 9P

- **Contexto.** La verificación de v2.4 evaluó los 9P en `t = ZoneTime`, pero el reloj de los 9P arranca en `y0 = 50 ft` y
  `ZoneTime` se mide desde la liberación. Con `t_s ≈ −0.026 s` el error esperado en `y` es `|vy|·|t_s| ≈ 3.5 ft`; se
  observaron 4.27 ft de mediana. El error de 1.29 ft en `PlateLocSide` es demasiado grande para venir solo del tiempo
  (`|vx|·|t_s| ≈ 0.15 ft`): apunta a un **signo invertido** entre `x` y `PlateLocSide`. ROADMAP §1.3.
- **Decisión.** El tiempo al plato `t_p` **no** es `ZoneTime`: es la raíz positiva menor de `y(t_p) = y_p` con la
  trayectoria 9P (`fisica.tiempo_al_plato`). El plano `y_p ∈ {17/12, 0}` ft y el signo `s ∈ {+1, −1}` en
  `PlateLocSide = s·x(t_p)` se **eligen por mínimo error mediano** contra `PlateLoc*` (`fisica.calibrar_plano_y_signo`; el
  reporte trae la tabla de las 4 combinaciones). Verificación cruzada: `ZoneTime ≈ t_p − t_s`. La Prop. 1 de F2 usa
  `t_m = ½(t_s + t_p)`, el punto medio entre la liberación y el plato. Los valores vigentes viven en
  `config/default.yaml` (`fisica.y_plato_ft`, `fisica.signo_plateloc_x`); `pitcheo f00 --aplicar` los reescribe con los
  elegidos por los datos.
- **Alternativas.** Suponer el plano y el signo (es justo lo que no se sabe); usar `ZoneTime` como reloj de los 9P (el error
  de v2.4).
- **Consecuencias.** G0.7: con el `y_p` y el signo elegidos, mediana de |error| ≤ 0.05 ft en `PlateLocSide` y
  `PlateLocHeight`, p99 ≤ 0.3 ft, y mediana de |`ZoneTime` − (`t_p` − `t_s`)| ≤ 0.005 s. La Prop. 1 de F2 calculaba el punto
  medio del vuelo con `ZoneTime` y lo habría puesto mal; ya está corregida.

## ADR-015 — Los outs que faltan son turnos finales perdidos, y no al azar

> **Estado: reemplazada en lo esencial por ADR-016 (ROADMAP §1.4).** G0.8 se sustituye por G0.8′, el estimador `π̂_K` se
> retira y «turno final perdido» pasa a llamarse «out faltante (sin turno incompleto)». Se conserva el texto original como
> historia de la decisión.

- **Contexto.** De las 4 763 medias entradas con 2 outs, solo el 9.5 % deja un turno incompleto (lo que dejaría un robo o un
  pickoff con 2 outs). El 90 % restante pierde **el último turno completo**: todos sus lanzamientos faltan. Comparadas con
  las de 3 outs tienen 0.525 ponches menos por media entrada y solo 0.388 outs en juego menos; si los turnos perdidos fueran
  un final al azar, la mayoría serían outs en juego. Es falta **no aleatoria** (MNAR). ROADMAP §1.3.
- **Decisión.** F0 clasifica cada media entrada **no final** de 2 outs en "turno incompleto" (hay un bateador con
  lanzamientos pero sin evento terminal) o "turno final perdido" (todos sus turnos terminan), y reporta la **tasa de turno
  final perdido por cubeta × año y por cubeta** (todos los años) con IC de Wilson, sobre las medias entradas no finales.
  **G0.8:** máx − mín entre cubetas ≤ 3 pp; si falla, es una **discrepancia y no se sigue a F1**: la pérdida de datos se
  confundiría con la altitud en cualquier comparación de resultados (F8). También reporta los déficits de eventos (K, OUT_BIP,
  SAC; 3 outs menos 2 outs) y `π̂_K = d_K/(d_K + d_OUT_BIP + d_SAC)` con IC por bootstrap de medias entradas (semilla fija,
  orden determinista). **No se implementan todavía los pesos de Horvitz–Thompson `ω`** (eso es F4), ni la Prop. 15.
- **Alternativas.** Tratar las de 2 outs como robos (contradice el 90 %); descartarlas (sesga a la baja los ponches con 2
  strikes y, con ellos, el valor de cada conteo).
- **Consecuencias.** Se aceptan las cotas con `π ∈ {0, π̂_K, 1}` de la Prop. 15, que no necesitan ningún supuesto sobre `π`.
  **Advertencia de identificación** (`docs/discrepancias/D01.md`): con datos sintéticos sembrados con `π_K` = 0.40, 0.71 y 0.93,
  el estimador de déficits devuelve ≈ 0.34, 0.30 y 0.30. Mide los ponches entre los terceros outs **registrados** y es
  insensible a la pérdida selectiva, así que `π̂_K` solo debe leerse como una estimación gruesa; el reporte añade los
  **ponches por out registrado** (2 vs 3 outs) y la dispersión por juego para contrastar la hipótesis.

## ADR-016 — Outs no contabilizados: `OutsOnPlay` no es un registro fiel de los outs

- **Contexto (ROADMAP §1.4, hallazgo 4).** En la tercera corrida real G0.8 falló: la tasa de medias entradas no finales con 2
  outs registrados y sin turno incompleto es 9.87 / 11.71 / 14.27 % (No / Medium / Extreme), con rango 4.40 pp estable en los tres
  años. La clasificación «turno final perdido» suponía que `OutsOnPlay` cuenta todos los outs. El dato lo contradice: solo ~280
  jugadas tienen `OutsOnPlay ≥ 2` (a tasa MLB se esperarían ≈ 3 470 dobles matanzas, luego ~92 % se registra como 1 out),
  `OutsOnPlay = 1` en el 100 % de los 30 648 ponches (el campo se asigna, no se registra), los conteos de medias entradas con 2
  outs por juego siguen una Poisson (φ = 1.10: un evento de juego a tasa constante, no una falla de sensor concentrada), su
  composición encaja con la doble matanza (K ≈ 0.37, OUT_BIP ≈ 1.6 y más BB, porque exige corredores) y el gradiente por cubeta
  tiene explicación física (más corredores en altura, más oportunidades de doble matanza).
- **Decisión.** Una media entrada no final con 2 outs registrados y todos sus turnos terminados se llama **«out faltante (sin
  turno incompleto)»** y se descompone en dos mecanismos con la **Prop. 16**: **U** (out no contabilizado: están todos los
  lanzamientos, pero un out real no está en `OutsOnPlay`) y **L** (turno perdido: faltan todos los lanzamientos de un turno que
  terminó en out). U no sesga ningún outcome por lanzamiento; L sí.
  - **Conjunto T:** medias entradas no finales, `Inning` ≤ 9, consistentes (outs registrados ≤ 3) y sin turno incompleto; el
    reporte dice cuántas excluye cada filtro (en cascada y aplicado solo). `O_h = Σ OutsOnPlay`, `P = {O_h = 2}`, `N_h` = turnos
    con evento 1B, 2B, 3B, BB, HBP o ROE y `Z = 1[N_h = 0]`.
  - **Prop. 16** (supuestos S1: un U exige corredor, luego `P(Z=1 | U) = 0`; S2: L quita un turno de out y es independiente de
    `Z` dentro de la cubeta): `f_b = P(Z | b)`, `p⁰_b = P(P ∧ Z | b)`, **`r̂_b = p⁰_b / f_b`** y **`θ̂_b = r̂_b / P(P | b)`**, por cubeta y
    global, con IC95 por bootstrap de **juegos** (1 000 réplicas, semilla de config; se remuestrea dentro de cada cubeta y la
    tabla va ordenada de forma determinista).
  - **Prop. 17:** `m̃_b` = turnos por media entrada de `T_b`; `n_b` = turnos de la cubeta; `κ̄` = K / turnos global (una sola
    cifra, no por cubeta; tanto `m̃_b`, `n_b` como `κ̄` se calculan sobre T). `W(Γ) = Σ_{b ∈ {Extreme, No}} Γ·r̂_b / (m̃_b + Γ·r̂_b)`
    con `Γ = 1` y `Γ = 2`, y `SE_ref = √(κ̄(1−κ̄)(1/n_Ext + 1/n_No))`.
  - **Reglas fijadas por el orquestador (no se ajustan; viven en `config/default.yaml`).** **G0.9** (mecanismo; se reporta siempre
    y no falla): `θ̂` global con IC95; **U dominante** si el IC95 superior ≤ 0.25, **L dominante** si el inferior ≥ 0.50, **mezcla**
    en otro caso (sin dato para clasificar → mezcla, la ruta conservadora). **G0.8′** (sustituye a G0.8): `W(Γ=2) ≤ 3.92·SE_ref`;
    si además `W(Γ=2) ≤ SE_ref` → `qa.perdida_ignorable = true`; si pasa sin eso → `false` y F8 reporta los contrastes con intervalo de
    Imbens–Manski; **si falla → discrepancia, no se sigue a F1**.
  - `pitcheo f00 --aplicar` escribe `qa.mecanismo_outs ∈ {U, L, mezcla}` y `qa.perdida_ignorable` (bool) en `config/default.yaml`,
    como ya hacía con `y_p` y el signo (ADR-014); los leen F4, F6 y F8. Los valores de partida son los conservadores (`mezcla`, `false`).
  - **Corroboraciones informativas (no son compuertas):** (a) % de rodados entre los OUT_BIP con `Outs` previo ∈ {0, 1}, P vs. T∖P;
    (b) columna `Outs` en P vs. T∖P (mínimo > 0, out terminal con `Outs` = 2, huecos); (c) logit de `1[h ∈ P]` sobre cubeta + año, sin
    y con `min(N_h, 5)`, errores agrupados por juego; (d) jugadas con `OutsOnPlay ≥ 2` contra las dobles matanzas esperadas a la tasa MLB
    (solo referencia); (e) `|P|` por juego contra una Poisson (`docs/figuras/f00/P_por_juego_vs_poisson.png`).
  - **Limpieza del reporte:** «turno final perdido» → «out faltante (sin turno incompleto)»; se elimina `π̂_K` del reporte y del
    Bloque (la tabla de déficits queda como informativa, igual que la tasa por cubeta del antiguo G0.8); I3 se marca «sustituida por
    G0.2 (ADR-010)»; I8 reporta, para cada tipo que falla, la mediana de `|HorzBreak|` por mano y lo marca «no informativo» si alguna es
    < 2 in (el tipo casi no rompe en horizontal y el signo de su media es ruido). No cambia el cumplimiento de I8.
  - Se **acepta D01**: `π̂_K` por déficits no está identificado y se retira. No se implementan pesos `ω` (F4).
- **Alternativas.** Seguir leyendo el out faltante como turno perdido (el dato real lo contradice en cinco puntos); descartar las
  medias entradas de 2 outs (selecciona contra el tráfico de corredores, que difiere por cubeta); usar la tasa de P por cubeta como
  compuerta (mide U + L juntos y falla aunque no falte ningún lanzamiento).
- **Consecuencias (§1.4).** U dominante: pesos `ω` de ADR-015 retirados (no falta ningún lanzamiento y `ω` inventaría ponches), F4.1
  usa el modelo **C** (todas las de T más el regresor `u_h = 3 − O_h` con `w_u ≤ 0`) como principal y el criterio A como
  sensibilidad, F4.2 sin pesos, G4.6 = A vs. C y G6.5 retirada. Mezcla o L: `ω` **por cubeta** con `M_b = r̂_b·|T_b|` y `π ∈ {0, 1}`
  (cotas), **sin** `π̂_K`; A principal y C sensibilidad. Si `perdida_ignorable = false`, todo contraste de outcomes observados entre
  cubetas se reporta además con intervalo de Imbens–Manski.
- **Transparencia de pre-registro.** Los diagnósticos usan el tráfico de corredores por cubeta, que no es el estadístico de
  ninguna H1–H6; H3 condiciona en EV×LA y usa valor de batazo.

---

## ADR-017 — G2.1 como estudio de simulación; Props. 3″ y rediseño de G2.3 (decisiones F2)

- **Contexto.** El Prompt 2 de F2 (Sonnet) se detuvo porque G2.1 —definida como "error sintético de recuperación de ρ < 1 %"
  en una sola corrida— salió 1.253 % con 45 juegos y 3 semillas (`docs/discrepancias/D02b.md` §1). El diagnóstico mostró que
  el **sesgo** del estimador es ≈ +0.2 % (persiste sin ruido de posición) y que lo que cruzaba el 1 % era **dispersión
  muestral** de una sintética chica (sd 0.4–0.5 % con 45 juegos; 0.10–0.14 % con 150). La implementación también reveló que
  la Prop. 3′(b) era imprecisa (el factor de giro, calculado con la rapidez medida, mete un término en δ^L−δ^D) y que la
  banda de Deming no detecta un sesgo de ±2 %.
- **Decisión.**
  1. **G2.1 es un estudio de simulación** (Morris, White y Crowther 2019) con protocolo pre-registrado y **no ajustable a la
     vista del resultado**: estimando log(ρ_nivel/ρ_No) por nivel; R = 10 réplicas con semillas fijas **101–110**, 150
     juegos/réplica y ~250 lanzamientos/juego (máximo factible ≥ 150 juegos si el costo lo impide, documentándolo).
     **Aprueba** si, por nivel, |sesgo relativo medio| + 1.96·MCSE < 1 %. Se reportan además SE empírico, RMSE y **cobertura
     del IC95 CR2** de δ̂_g sobre todos los juegos×réplicas (valida G2.4; alerta si < 0.90). La corrida fallida de 45 juegos
     queda como antecedente en D02b. Detalle en `docs/MODELO_MATEMATICO.md` §F2.5a.
  2. **Prop. 3″** (sustituye a la 3′(b), §F2.4): (i) solo el c_g **relativo** entre parques es identificable —la
     normalización por canal absorbe un c común, así que un sesgo uniforme no confunde contrastes de altitud—; (ii) como S
     usa la rapidez medida, **δ^L − δ^D = κ̄·c_g + (η_L − η_D)·log(λ/τ)**, con η_D ≈ 0 y η_L ≈ 0.47 (signos verificados en la
     sintética); (iii) separar λ de τ con ê queda **🔎 exploratorio, nunca compuerta**.
  3. **G2.3 se divide:** **G2.3a** = Deming, pendiente ∈ [0.85, 1.15] (proporcionalidad; se conserva). **G2.3b** = ĉ por
     parque con el detector ê (ID de parque de F0, o parque latente GMM), centrado en la mediana de su cubeta, con **Wald
     (SE CR2) y control FDR de Benjamini–Hochberg al 5 %**; criterio **potencia ≥ 0.80 para |c| = 0.02 y FPR ≤ 0.05** en
     parques limpios, medido inyectando λ = 1.02 en ~1/3 de los parques de cada cubeta y τ = 1.01 en otro ~1/3 (§F2.5b).
  4. **ê = v̂ × n̂_Magnus**, con n̂_Magnus la dirección de **sustentación** implicada por `SpinAxis` (convención Nathan 2008),
     no el vector del eje. La prueba de **circularidad de `SpinAxis`** (R² sobre columnas de movimiento) es **obligatoria**;
     si sale inferido, **G2.3b se declara no evaluable** y queda solo G2.3a.
  5. **Solver** para la Prop. 2′: LSMR disperso (Fong y Saunders 2011) o aceleración Irons–Tuck (Bergé 2018), que debe
     coincidir con las proyecciones alternadas a ≤ 1e-8 en la muestra de 5 000 (prueba de regresión).
- **Alternativas.** Subir el tamaño de la sintética o cambiar semillas para que la corrida de 45 juegos "pasara" habría sido
  ajustar la compuerta al resultado: rechazado. Dejar G2.3 solo como Deming habría dejado pasar sesgos de calibración de
  ±2 % específicos de parque, que es justo la amenaza de la Prop. 3 (b).
- **Consecuencias.** F2 (Sonnet) implementa estas compuertas; nada de esto se implementa en esta ronda del orquestador (solo
  docs + el experimento de D02b §3). G2.3b depende de que exista ID de parque o un GMM de parques latentes y de que
  `SpinAxis` sea medido. La corrida local de F2 queda a la espera de la implementación.

---

## ADR-018 — Prop. 2″ (Reynolds), normalización por año, fail-closed de SpinAxis y rediseño de G2.3b (ronda 3 de F2)

- **Contexto.** La corrida sobre datos reales de ADR-017 (`reports/FASE_02.md` en 6a4d3ee) dejó cuatro hallazgos:
  (i) `verificar_spinaxis_medido` reportó los tres criterios como `NaN` y, por `nan < 1.0 == False`, declaró el eje **medido**;
      la máscara de validación no filtraba SpinAxis nulo ni vectores perpendiculares degenerados.
  (ii) **Deming δᴸ sobre δᴰ = 1.514** (EE 0.019 por dos vías, z vs 1 = 26.6; `n = 2 112` juegos): muy fuera de la banda
      [0.85, 1.15]. En paralelo, **δ̄ᴰ Extreme = −0.159**, mientras la predicción barométrica a 2 000 m es
      log(ρ₂₀₀₀/ρ₀) ≈ −0.240. Ambos síntomas apuntan a la misma causa física: **atenuación por dependencia de los
      coeficientes aerodinámicos en el número de Reynolds** (ley potencial local alrededor del drag crisis; Nathan 2008,
      *Am. J. Phys.*). Si log C_c = f_c(S,k,h,year) + β_c · log Re + …, entonces δ̂_c = (1 + β_c) · log ρ_g; con
      β_D ≈ −0.34 y β_L ≈ 0 se obtiene δ̂ᴸ/δ̂ᴰ = (1+β_L)/(1+β_D) ≈ 1.52, consistente con 1.514 observado.
  (iii) El modelo de ADR-017 fuerza `mean(δ : No Altitude) = 0` globalmente, pero los juegos están **anidados en el año**:
      cambios anuales (p. ej. pelota) actúan como un γ_year colineal con δ_g, y el nivel global absorbe su media.
  (iv) G2.3b (ADR-017: mediana por cubeta, Wald + BH, cluster lanzador-dentro-del-juego) dio **FPR 0.167 (10/60)** en la
      sintética; el diagnóstico (`docs/discrepancias/D02b.md` §4) atribuyó el exceso a dos cosas: el conglomerado trata
      los juegos de un mismo lanzador como independientes aunque sus errores de α_{j,k} se correlacionan, y la mediana
      por cubeta deja los contrastes de limpios por pares con signos opuestos.
- **Decisión.**
  1. **Fail-closed de SpinAxis** (A, fija (i)). Antes de aplicar los tres criterios se exige una máscara por fila:
     `SpinAxis` finito, `v̄` finita y > 0, `ã` finita y norma de la perpendicular `l_perp` > 10⁻⁶ m/s². Si tras aplicarla
     quedan < 100 filas, o < 50 % de la entrada, el eje se declara **no evaluable** (`no_evaluable = True`, `medido =
     False`). Si algún criterio devuelve `NaN` tras el filtro, también se declara no evaluable. **G2.3b sobre datos reales
     es siempre informativa (🔎), nunca compuerta**: su veredicto `n/e` se dispara también por `no_evaluable`, por eje
     inferido (R² ≥ 0.95; umbral calibrado con el caso `spinaxis_inferido=True` de la sintética) o por falta de id de
     parque (cae a parque latente por GMM, exploratorio). La **compuerta G2.3b vive en la sintética**; su chk se corre
     dentro de cada réplica. Si la sintética sale inferida, la compuerta queda n/e, y se reporta.
  2. **Normalización por año** (B, fija (iii)). `estimador_densidad_juego` acepta `anio_juego` por juego; impone
     δ̄ _{referencia, year = y} := 0 **por cada año de la referencia** y expone `grupos_norm` (etiqueta por juego) y
     `niveles_por_grupo` por respuesta. Un año sin juegos de referencia usa la media de los niveles disponibles
     (fallback declarado). El SE CR2, `c_g_desde_diferencia` y `c_g_detector_e` aceptan `grupos_norm` y construyen el
     contraste por grupo. Medias por cubeta: media de las medias por año ponderadas por juegos de la cubeta en el año;
     contrastes contra la referencia: diferencia dentro del año con los mismos pesos. Los años se leen de `d["year"]`
     (constante por juego). ADR-017 queda como `por_anio = false` (compat).
  3. **Prop. 2″** (C, fija (ii)). Modelo ampliado `y_c = δ_g + α_{j,k} + f_c(S) + β_c · log‖v̄‖ + ε`. β_c se identifica
     con la variación de log‖v̄‖ **dentro de lanzador×forma** (controlada por el spline de S y por las dummies de juego).
     Ajuste por LSMR disperso con una columna extra (precondicionada); SE CR2 con conglomerado **lanzador × juego** para
     β y para los contrastes de δ. Diagnóstico de colinealidad: R² de log‖v̄‖ sobre {dummies juego, lanzador×forma,
     splines de S}. R² ≥ `tolerancia_r2_colinealidad` (default 0.98) ⇒ β no identificable, Prop. 2″ no adoptada.
     **Sobreidentificación pre-fijada**: `|p − b| + 1.96 · √(Var(p) + Var(b)) < tolerancia_equivalencia` (default 0.10),
     con `p = (1 + β̂_L) / (1 + β̂_D)` y `b` la pendiente de Deming observada. Var(p) por delta method sobre β̂_D y β̂_L;
     se asume Cov(β̂_D, β̂_L) = 0 entre respuestas (conservador, η correlacionados). **Si pasa**: δ̃_c = δ̂_c / (1 + β̂_c),
     SE con delta method CR2 sobre el contraste combinado, se adopta como **primario para G2.2 y G2.4**; la pendiente
     de Deming sobre δ̃ debe estar cerca de 1 por construcción (reportada como diagnóstico). **Si no pasa** (o β no
     identificado, o Prop. 2″ desactivada): δ̂ bruto sigue como primario (compuertas pueden fallar como en 6a4d3ee) y
     se **DETIENE** la fase. Robustez: la versión no lineal de punto fijo (spline en log Re iterado) queda documentada
     en MODELO_MATEMATICO §F2.3bis como aproximación de orden superior; no se adopta en esta ronda.
  4. **G2.3b rediseñado** (D, fija (iv)). Sobre la sintética (único rol de G2.3b como compuerta):
     - **Conglomerado = lanzador** (Cameron y Miller 2015, *J. Hum. Resour.*): el nivel más agregado donde los errores
       siguen correlacionados; refleja que α_{j,k} de un lanzador se repite en todos sus juegos y parques.
     - **Contraste leave-one-out** por parque: h_p = c_p − media(c_q : q ≠ p ∧ cubeta(q) = cubeta(p)). Lineal en {c_p},
       la covarianza CR2 conjunta es exacta y el parque mediano con conteo impar deja de ser un caso especial.
     - **t de Pustejovsky y Tipton (2018)**: df Satterthwaite usando las contribuciones de componentes CR2 por cluster,
       df_PT ≈ (Σ_c s_c²)² / Σ_c s_c⁴ (aproximación conservadora de la fórmula exacta del paper); p-value t de dos colas.
     - **BH 5 %** sobre los parques evaluables; potencia ≥ 0.80 (global y por tipo: λ=1.02, τ=1.01); FPR ≤ 0.05 en
       parques limpios.
     - **Sintética con Reynolds explícito** (D). `generar_fisica` acepta `beta_D`, `beta_L`: aplica una ley potencial a
       C_D (C_L) sobre ρ·v. β_D = −0.30 por default en config (plausible para el drag crisis, Nathan 2008). Confirma que
       sin corrección el estimador se atenúa y con corrección recupera ρ.
     - **Semillas 201–210** (las 101–110 quedaron consumidas en D02b §4). Si se adoptara otro cambio a futuro (p. ej.
       cambiar el cluster o un umbral de G2.3b), **otro bloque de semillas pre-registradas**.
- **Alternativas.** Dejar las compuertas de ADR-017 y declarar que F2 falló en real: rechazado — hay una explicación
  física simple (drag crisis) y un estimador identificable para corregirla. Añadir γ_year como columna explícita al
  diseño: equivale a la normalización por año post-hoc elegida (menos columnas, misma información). Mantener el cluster
  lanzador-dentro-del-juego en G2.3b: rechazado por el diagnóstico de D02b §4 (sd(z) = 1.28, no 1).
- **Consecuencias.** Prop. 2″ es parte permanente de F2 cuando β esté identificado; los artefactos para F3 (`δ̃_g`, con
  su SE) sustituyen a los antiguos `δ_g`. G2.3b sobre datos reales es siempre `n/e` (nunca ❌), consistente con el hecho
  de que F0 no trae id de parque; la compuerta se evalúa en la sintética. La normalización por año no afecta a los
  estimadores sintéticos de la antigua ronda 2 (modo global queda disponible como `por_anio: false`). La corrida real
  queda a la espera: F2 (Rodrigo) corre `scripts/fases/f02.sh` con el código nuevo.

---

## ADR-019 — Generador Re-puro, protocolo sintético R=30, cotas de Morris–White–Crowther, regla de detención en real y recursos de cómputo (ronda 4 de F2)

- **Contexto.** La corrida pre-registrada de ADR-018 (semillas 201–210, β_D=−0.30 en el generador; D02c §8) dejó G2.1 sobre δ̃
  en 1.5–2.1 %, cobertura 0.79 y G2.3b con FPR 0.067 (4/60). El diagnóstico atribuyó el 2 % al sesgo de β̂_D (−0.346) y a un
  término aditivo `C_D·(1+0.2(v/40−1))` del generador que no es una ley potencial pura; el FPR, a una cota de 0.05 a secas
  sobre solo 60 parques limpios. El orquestador decidió D1–D4 y fijó recursos para la laptop de Rodrigo (i7-1165G7, 4 núcleos
  físicos / 8 hilos, 32 GB), que debe quedar usable durante F2.
- **Decisión (orquestador).**
  1. **D1 — Generador Re-puro.** `C_D = C_D(Re)` con Re = ρ·v·d/μ y ley potencial pura de pendiente local β_D = −0.30 en log Re, sin
     ningún otro término en v; `C_L(S)` sin Re (β_L = 0). El término aditivo se elimina.
  2. **D2 — R = 30 réplicas, semillas NUEVAS 211–240.** Las semillas **101–110** (D02b §4) y **201–210** (D02c §8) están
     **consumidas** y no se reutilizan. G2.1 sobre δ̃ con el mismo criterio (|sesgo relativo medio| + 1.96·MCSE < 1 % por nivel).
  3. **D3 — G2.3b:** FPR ≤ 0.05 + 1.96·√(0.05·0.95/n_limpios) (Morris, White y Crowther 2019 §5.2; con n = 180 limpios, 0.0818),
     reportando el IC exacto de Clopper–Pearson; potencia ≥ 0.80 (global y por tipo). Sin cambios de método respecto a ADR-018
     (LOO, cluster lanzador, t de Pustejovsky y Tipton, BH 5 %).
  4. **D4 — G2.4:** cobertura del IC95 sobre **δ̃** con el SE delta que incluye Var(β̂), ≥ 0.90. La equivalencia de pendientes
     (1+β̂_L)/(1+β̂_D) en la sintética es **solo informativa**.
  5. **E — Datos reales:** la equivalencia contra la Deming observada (±0.10) **decide**. Si pasa, δ̃ es primario para G2.2–G2.4.
     Si no, G2.2–G2.4 se reportan en bruto con 🔎 (provisionales) y la fase **se DETIENE** (`detenido`, salida 2).
  6. **R — Recursos:** `recursos.n_jobs: 3` por defecto (nunca −1; se acota a los núcleos físicos); BLAS a 1 hilo dentro de cada
     worker (`threadpoolctl`/`parallel_config(inner_max_num_threads=1)` y `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1` en `f02.sh`) y
     ≤ 4 hilos de BLAS en el proceso principal; caché en disco de la sintética (`reports/cache/f02_sint/*.npz`, en `.gitignore`;
     llave = config + semilla + hash de `sintetico.py`/`fisica.py`; `--sin-cache`); `f02.sh --etapa pruebas|escala|sintetica|real|todo`
     (`todo` salta la escala si existe `reports/f02_escala.json` con el mismo hash de código), `nice -n 10 ionice -c3`,
     `--cpu-max 300` vía `systemd-run --user --scope -p CPUQuota=300%` si está disponible; trap de SIGINT/SIGTERM que mata los
     workers de loky y **no commitea** si una etapa fue interrumpida (con `--commit`); `reports/f02_recursos.json` con tiempo, RAM
     pico (incluidos los hijos, psutil) y CPU % promedio por etapa (meta ≤ 75 % del equipo).
- **Hallazgos de la implementación (cambios de diseño NO pedidos; propuestos para ratificación).**
  1. **log‖v̄‖ es endógeno** (D02c §9.1). Con el generador Re-puro y β_D = −0.30, MCO da β̂_D ≈ −0.53: sesgo −0.24 que **persiste sin
     ruido de posición** y desaparece solo si se quita la heterogeneidad por lanzamiento de C_D (con σ_α = σ_ε = 0, MCO recupera −0.300
     exacto). Mecanismo: un C_D mayor frena más y baja ‖v̄‖ (punto medio), justo cuando y = log ρC_D sube. La prueba pedida («β̂_D
     recupera −0.30, sesgo < 2·SE») es imposible con MCO.
  2. **Estimador: 2SLS** con log(RelSpeed) (rapidez en la liberación, medida antes del vuelo) como instrumento de log‖v̄‖ (primera
     etapa F > 7·10⁵). `RelSpeed` está en el diccionario del organizador. Sin `RelSpeed` utilizable, cae a MCO y lo declara.
  3. **S = rω/v̄ es un control endógeno** (hereda la parte endógena de v̄): con S medida el 2SLS conserva un sesgo de +0.034
     (|z|>2 en 3/12 réplicas); con **S_rel = rω/RelSpeed** en el spline del modelo de Reynolds, +0.007 y sd/SE = 0.91 (|z|>2 en 0/12).
     Se adopta S_rel solo en el modelo de Reynolds (`prop2pp.s_exogeno`); el estimador bruto de la Prop. 2′ no cambia.
  4. **La equivalencia (±0.10 con 1.96·SE) casi no tiene potencia con ≈ 3.7·10⁴ lanzamientos:** SE(p) ≈ 0.06 ⇒ |dif| + 1.96·SE > 0.10
     aun con diferencia 0.004 (piloto: predicha 1.408 vs observada 1.412, 0/6 aprueban). Por eso es solo informativa en la sintética.
     Con ≈ 6.3·10⁵ lanzamientos el SE cae ≈ √17 veces y la prueba sí discrimina. Alternativa si el orquestador la quiere más permisiva:
     TOST al 90 % (1.645·SE).
- **Alternativas.** Bajar R o cambiar semillas hasta pasar: rechazado. Mantener MCO y relajar la prueba de G: rechazado (el sesgo es
  de método, no de muestra). Instrumentar con vy0 (velocidad del 9P a 50 ft): no probado; por razonamiento, ya acumula 4.5 ft de arrastre y seguiría parcialmente endógeno.
- **Consecuencias.** δ̃_g (con su SE delta) sustituye a δ_g como insumo de F3 cuando la equivalencia pasa en real. La etapa `real`
  depende de `reports/f02_sintetica.json` (firma = config + código).
- **Resultado (D02c §10).** Protocolo pre-registrado (semillas 211–240, código congelado en e287d3f; `f02.sh --etapa sintetica`):
  **G2.1** sobre δ̃ 0.305 % (Medium) / 0.410 % (Extreme) ✅; **G2.3b** potencia 1.000 (IC95 CP [0.990, 1.000]) y FPR 4/180 = 0.022
  (IC95 CP [0.006, 0.056]; cota 0.0818) ✅; **G2.4** cobertura 0.948 ✅. β̂_D = −0.304 (verdad −0.30; MCO −0.562). Sin corregir, el δ̂ bruto
  se atenúa 5.9 % / 8.3 % con cobertura 0.468. Una segunda corrida con la caché dio resultados idénticos (226 s vs 492 s). Escala (≈ 635 k
  lanzamientos, pipeline completo): 210 s, 2.6 GB, CPU 52 %. Etapa `real` de punta a punta sobre una sintética de esa escala: 197 s; la
  equivalencia pasa (frontera 0.031) y δ̃ recupera los niveles barométricos. **Pendiente:** la etapa `real` sobre los datos reales (Rodrigo).
- **Por ratificar (orquestador):** (a) 2SLS con `RelSpeed` y S_rel en lugar de MCO (hallazgos 1–3); (b) equivalencia ±0.10 con 1.96·SE o TOST
  al 90 %; (c) que `real` falle cerrado a MCO si `RelSpeed` falta (β̂ sesgado a la baja, declarado en el reporte).

---

## ADR-020 — Prop. 2‴: canal de sustentación primario (ρ̂ᴸ con β_L = 0); el 2SLS del canal D queda como diagnóstico; nueva G2.3a de consistencia física

- **Contexto.** La corrida sobre datos reales con ADR-019 (`reports/fase_02.json` en 6f8761c) ejecutó el 2SLS con `RelSpeed` como
  instrumento de log‖v̄‖ y produjo **β̂_L = +0.62 ± 0.04** (primera etapa F = 2.1·10⁷; MCO: β̂_L = +0.38). Un β_L positivo tan grande
  **contradice la literatura** del coeficiente de sustentación de la pelota de béisbol: C_L ≈ C_L(S) con una dependencia de Reynolds
  despreciable en el rango típico (p. ej. Nathan 2008, *The Effect of Spin on the Flight of a Baseball*, Am. J. Phys. 76(2);
  Alaways y Hubbard 2001, *Experimental Determination of Baseball Spin and Lift*, J. Sports Sci. 19). Tres canales explican el
  valor empírico sin invocar un efecto físico que no existe:
  1. **Falla de exclusión del instrumento dentro de lanzador** (Angrist y Pischke 2009, *Mostly Harmless Econometrics*, cap. 4):
     `RelSpeed` no solo mueve el drag; a lanzador fijo capta **esfuerzo** (variaciones de salida máxima lanzamiento a lanzamiento) y
     **eficiencia de giro** (correlación empírica entre velocidad de liberación y spin bajo esfuerzo). Esos canales entran en el error
     estructural de la ecuación del canal L (y de C_D de alto Re) y rompen la exclusión del IV. Si log(RelSpeed) está correlacionado
     con la parte de η_L no modelada, β̂_L^IV queda sesgado y no estima dC_L/d log Re.
  2. **SpinAxis inferido impide controlarlo.** En los datos reales R²(SpinAxis | movimiento) dentro de lanzador×forma = **0.998**,
     declarado inferido (ADR-018). No se puede añadir controles de eficiencia de giro independientes del movimiento.
  3. **La sintética no tenía esa heterogeneidad.** El generador fija C_L = C_L(S) sin acoplamiento a esfuerzo, así que la validación
     sintética del 2SLS no detectaba la falla.
  Registrado en `docs/discrepancias/D02d.md`.
- **Decisión.**
  1. **ρ̂_g / ρ_ref := exp(δ̂ᴸ_g)** con β_L = 0 (Prop. 2‴). δ̂ᴸ es el estimador bruto del canal L; nada se ajusta a esa estimación.
  2. **El canal D es secundario.** 1+β_D por cubeta se **implica** del ratio de medias ponderadas por año (ADR-018 §B):
     `1+β̂_D (c) = δ̄ᴰ(c) / δ̄ᴸ(c)`, con SE delta de dos vías (Cov(δ̄ᴰ,δ̄ᴸ) ≈ 0; conservador, se declara).
  3. **2SLS = diagnóstico 🔎.** Prop. 2″ (ADR-019) permanece en el reporte, pero **no decide la adopción**; sus β̂ se presentan como
     diagnóstico de endogeneidad y de la falla de exclusión. ADR-019 §C ("si pasa la equivalencia, δ̃ es primario") queda sobreseído.
  4. **Compuertas** (MODELO_MATEMATICO §F2.7 y `config/default.yaml`; **sin cambios en las bandas de G2.2 ni G2.4**):
     - **G2.1** mide la recuperación de ρ con **δ̂ᴸ bruto**, mismo criterio Morris–White–Crowther (|sesgo relativo| + 1.96·MCSE < 1 %).
       Semillas NUEVAS **241–270** (R = 30). **Consumidas** y no reusables: 101–110 (D02b §4), 201–210 (D02c §8) y 211–240
       (D02c §10 / ADR-019). El generador corre con β_D = −0.30, β_L = 0 **y** calibración por parque (λ = 1.02 en 1/3 y τ = 1.01
       en otro 1/3 por cubeta): el escenario incluye la realidad que ADR-018 §F2.5b probaba por separado.
     - **G2.2** se evalúa sobre δ̂ᴸ, bandas de ADR-017.
     - **G2.3a** sustituye a la Deming: **consistencia física del canal D**: 1+β_D implícito por cubeta ∈ **[0.30, 1.00]** en Medium
       y en Extreme (margen amplio: la crisis de arrastre, Nathan 2008, pone a C_D en descenso con log Re pero no fija un valor).
       La igualdad entre cubetas (Wald sobre los ratios) se reporta como 🔎, **no es compuerta**: la crisis es no lineal.
     - **G2.3b sin cambios** (validación sintética con cluster lanzador + LOO + Pustejovsky–Tipton, ya ✅ en ADR-019; se reutiliza).
     - **G2.4** se mide sobre **δ̂ᴸ**: SE CR2 mediano de δ̂ᴸ_g < 0.03 **y** cobertura ≥ 0.90 en la sintética 241–270.
     - **Nuevo informativo:** sesgo por parque de δᴸ inducido por c_g, contra la predicción κ̄·c (Prop. 3′).
  5. **Declaración explícita.** Esta es una **enmienda post-datos**: observar β̂_L = +0.62 motivó revisar el estimador. Como advierte
     Gelman y Loken (2013, *The Garden of Forking Paths*), un cambio de método a la vista del resultado puede inflar la aparente
     confianza; para mitigarlo se eligen **semillas nuevas** 241–270, se mantiene el criterio de G2.1 (1 %), se mantienen las bandas
     de G2.2 y G2.4, y la enmienda queda registrada aquí y en D02d con la hipótesis identificable (falla de exclusión) y la
     validación sintética independiente.
  6. **Cadena hacia abajo.** F3 en adelante deben correr su análisis **primario con ρ̂ᴸ** y reportar **ρ̃ᴰ = ρ̂ᴸ · (1+β̂_D(c))** como
     sensibilidad por cubeta (actualizado en ROADMAP §4-F3 y ADR). "Reportar ambos" es parte del contrato de las compuertas de F3+.
- **Alternativas.** Mantener Prop. 2″ con un instrumento distinto (vy0 del 9P a 50 ft): descartado por razonamiento (acumula ya
  parte del arrastre). Reparametrizar C_L en el estimador con un término explícito de "esfuerzo" (p. ej. SpinRate centrado por
  lanzador): no identificable con SpinAxis inferido. Dejar la Deming como compuerta: sobreseído: el ratio 1.52 era síntoma de la
  misma dependencia de Re en el canal D, no de un problema de calibración.
- **Consecuencias.** F2 cierra en lift-primary. F3 arranca con la regla de doble canal. Los artefactos para F3+ son `ρ̂ᴸ` (primario,
  con su SE CR2) y `1+β̂_D(c)` (SE delta). El 2SLS queda documentado en el reporte y en D02d como diagnóstico; su no uso para
  decidir se registra con la referencia a Angrist y Pischke 2009 (falla de exclusión) y Gelman y Loken 2013 (enmienda post-datos).
