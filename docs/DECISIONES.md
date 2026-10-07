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
