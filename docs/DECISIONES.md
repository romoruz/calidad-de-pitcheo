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
