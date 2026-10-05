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
