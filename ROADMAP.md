# ROADMAP MAESTRO — Stuff+ LMB calibrado por densidad del aire

**Proyecto:** Hackathon ISAC 2026 · Reto Diablos Rojos · `romoruz/calidad-de-pitcheo`
**Versión:** 2.10 (2.9 + decisiones F2: G2.1 como estudio de simulación, Prop. 3″, G2.3a/G2.3b; ADR-017)
**Ruta local (clon del repo + datos):** `/home/rodrigo/calidad-de-pitcheo`
**Regla:** solo el orquestador cambia este archivo. Claude Code lo lee, no lo edita.

---

## Estado por fase

| Fase | Estado | Rama / tag / nota |
|---|---|---|
| F0.0 | ✅ cerrada | tag `fase00_0` |
| F0 | ✅ cerrada (G0.1–G0.9) | merge `45f9f7c`, tag `fase00`; mecanismo U, `perdida_ignorable=false` |
| F1 | ✅ cerrada (pre-registro H1–H6) | merge `b6a008c`, tag `fase01`; BH m=5, H5 por equivalencia (v2.8) |
| F2 | 🟡 diseño revisado (Props. 1, 2′, 3″) + implementación en curso | rama `fase02`, sin PR; compuertas G2.1 (estudio de simulación), G2.2, G2.3a/b, G2.4 por implementar (Sonnet) |
| F3 | ⚪ pendiente | diseño (Opus) tras F2 |
| F4 / F5 | ⚪ pendientes (paralelizables) | dependen de F2–F3 |
| F6–F11 | ⚪ pendientes | — |

---

## Índice

0. [Cómo se usa](#0-cómo-se-usa)
1. [Lo que el diccionario cambia del plan](#1-lo-que-el-diccionario-cambia-del-plan)
2. [Notación y constantes](#2-notación-y-constantes)
3. [Grafo de fases](#3-grafo-de-fases)
4. [Fases F0–F11](#4-fases)
5. [Protocolo de orquestación](#5-protocolo-de-orquestación)
6. [Registro de riesgos](#6-registro-de-riesgos)

---

## 0. Cómo se usa

### 0.1 Tres lugares, tres papeles

Es el mismo esquema que `Historia-de-un-entrenador`: **el código y los resultados agregados viven en GitHub; los datos nunca.**

| Lugar | Quién | ¿Ve los datos? | Hace |
|---|---|---|---|
| **Claude Code en chat** (claude.ai/code o la app), conectado a `romoruz/calidad-de-pitcheo` | Opus o Sonnet, con el selector de modelo | **No** | Escribe código, pruebas con datos **sintéticos**, el script de cada fase y la documentación. Entrega en una rama con PR |
| **Laptop de Rodrigo** (`/home/rodrigo/calidad-de-pitcheo`, clon del repo) | Rodrigo | **Sí**, en `data/raw/` (fuera de git) | Baja la rama, corre el script de la fase, sube solo reportes, `.json` de cifras y figuras agregadas |
| **Chat del orquestador** (este chat) | Claude | No | Recibe Bloques, decide discrepancias, versiona este archivo |

| Rol | Modelo | Hace |
|---|---|---|
| Arquitecto / auditor | **Opus** | Diseño matemático, auditoría de fugas, validación, revisión de resultados, redacción |
| Implementador | **Sonnet** | Código, pruebas, generador sintético, figuras, refactors |

### 0.2 Ciclo de cada fase

```
 Claude Code (chat)                Laptop (local)                    Claude Code (chat)
 ───────────────────               ─────────────────                 ───────────────────
 prompt + sufijo §0.3   ──PR──►    git switch faseXX        ──push──► prompt de revisión §0.4
 código + tests sintéticos         bash scripts/fases/fXX.sh          ¿compuertas OK?
 rama faseXX                       git add reports/ docs/figuras/      ├─ sí → merge a main + tag
                                   git push                            └─ no → DXX.md → orquestador
```

**Comandos locales de cada fase** (Claude Code los repite al final de su respuesta con el número correcto):

```bash
cd /home/rodrigo/calidad-de-pitcheo
git fetch origin && git switch faseXX && git pull
bash scripts/fases/fXX.sh
git add reports/ docs/figuras/ && git commit -m "fase-XX: resultados locales" && git push
```

Si el script truena en local, pega en el **mismo hilo de Claude Code** las últimas 60 líneas de `reports/logs/fXX_*.log` con el prompt de error (§0.5).

### 0.3 Sufijo estándar (se pega al final de **todo** prompt de fase)

```text
CONDICIONES DE ESTE ENTORNO
- Trabajas en Claude Code (chat) sobre romoruz/calidad-de-pitcheo. NO tienes los
  datos reales: viven solo en la laptop de Rodrigo, en data/raw/, fuera de git.
- Lo que el prompt pida "sobre datos reales" lo escribes como código que ejecuta
  scripts/fases/fXX.sh; Rodrigo lo corre en local.
- Valida todo con el generador sintético src/pitcheo/sintetico.py, que respeta el
  esquema de docs/diccionario.csv. pytest -q debe pasar aquí antes de entregar.
- scripts/fases/fXX.sh debe: (1) exportar UV_PROJECT_ENVIRONMENT=$HOME/.venvs/
  calidad-de-pitcheo; (2) correr `uv run pytest -q`; (3) correr `uv run pitcheo fXX`;
  (4) escribir reports/FASE_XX.md con el Bloque para el orquestador y los .json de
  cifras; (5) figuras agregadas en docs/figuras/fXX/; (6) log fechado en
  reports/logs/; (7) salir con código ≠ 0 si una compuerta falla, después de
  escribir el reporte.
- Nunca filas por lanzamiento en reports/, logs ni figuras. Tablas por lanzador solo
  en reports/privado/ (fuera de git). Los logs imprimen formas y agregados, no filas.
- Entrega en la rama faseXX con PR a main. Termina tu respuesta con el bloque exacto
  de comandos locales (ROADMAP §0.2) con el número de fase correcto.
```

### 0.4 Prompt de revisión estándar (mismo hilo, después de la corrida local)

```text
Rodrigo ya corrió la fase XX en local y subió los resultados a la rama faseXX.
Haz git pull. Lee reports/FASE_XX.md, sus .json y el último log. Evalúa cada
compuerta de ROADMAP §4-FXX con las cifras reales y llena el Bloque para el
orquestador. Si todas pasan y no hay discrepancias de tipo B, C o D (§5): merge del
PR a main y tag faseXX. Si no: escribe docs/discrepancias/DXX.md, NO hagas merge y
dime exactamente qué pegarle al orquestador.
```

### 0.5 Prompt de error estándar (si el script truena en local)

```text
El script de la fase XX falló en local con datos reales. Abajo está la cola del log.
Diagnostica la causa sin pedir los datos: usa el esquema de docs/diccionario.csv y
reports/FASE_00_0.md. Si el problema es un supuesto sobre los datos que el sintético
no reproducía, corrige primero el generador sintético para que reproduzca el caso y
agrega una prueba que lo cubra; luego corrige el código. Push a la misma rama.
<pegar aquí las últimas 60 líneas del log>
```

### 0.6 Configuración inicial (una sola vez, en local)

La carpeta ya existe con `data/raw/` y archivos del explorador. Se convierte en el clon del repo:

```bash
sudo pacman -S --needed git uv github-cli
gh auth login                     # una vez: autentica git con tu cuenta de GitHub
cd /home/rodrigo/calidad-de-pitcheo
# ROADMAP.md, CLAUDE.md y el diccionario en su lugar
mkdir -p docs && cp ~/Descargas/stuff_plus_data_dictionary.csv docs/diccionario.csv
mv ~/Descargas/ROADMAP.md ~/Descargas/CLAUDE.md .
# fuera de git: datos, salidas del explorador, credenciales, entorno
cat >> .gitignore <<'EOF'
data/
artefactos/
reports/privado/
*.parquet
*.pkl
*.rds
explora.py
salidas/
credenciales.env
.venv*/
EOF
git init -b main
git add .gitignore ROADMAP.md CLAUDE.md docs/diccionario.csv
git commit -m "fase-inicio: roadmap, reglas y diccionario"
git remote add origin https://github.com/romoruz/calidad-de-pitcheo.git
git push -u origin main
git status --ignored | grep data/   # debe aparecer como ignorado
```

Después: en claude.ai/code, conectar el repo `romoruz/calidad-de-pitcheo` y empezar con F0.0.

## 1. Lo que el diccionario cambia del plan

| # | Hallazgo en el diccionario | Consecuencia | Decisión v2 |
|---|---|---|---|
| 1 | Cinemática 9P completa (`x0…az0`) y polinomios `PitchTrajectory{X,Y,Z}c{0,1,2}` | La Capa 1 es exacta | **ρ se estima por juego desde la propia trayectoria** (F2). Es el núcleo del proyecto |
| 2 | **No hay estadio, fecha ni clima.** Solo `altitude_category` y `year` | No hay *park holdout* real ni unión con Open-Meteo | Densidad por juego $\hat\rho_g$ (F2) + clases de densidad latentes. "Harp Helú" se define por **densidad**, no por cubeta (ADR-005) |
| 3 | **No hay corredores ni orden de lanzamientos** | RE24 imposible | Pesos lineales por regresión de media entrada + cadena de Markov de **conteos**, que no necesita orden (F4) |
| 4 | Sin secuencia | `prev_pitch_type` imposible | Túnel **estático** con los polinomios de trayectoria (F5) |
| 5 | `EffectiveVelo`, `VertApprAngle`, `HorzApprAngle` dependen de la ubicación | Fuga de ubicación hacia Stuff+ puro | Sustituir o residualizar (F5) |
| 6 | `ZoneSpeed`, `SpeedDrop`, `ZoneTime`, `*Break`, `pfx*` dependen de ρ | Son los **canales** del efecto altitud | Se transforman con el operador $T$ en el contrafactual (F3) |
| 7 | Columnas deterministamente redundantes | Riesgo de colinealidad, pero útiles para QA | Identidades I1–I8 como pruebas (F0) |
| 8 | IDs anónimos marcados `grouping_only` | Memorización si se usan como feature | Solo para CV, agregación y features relacionales de arsenal (solo física) |
| 9 | Targets ricos: `is_*`, `ExitSpeed`, `Angle`, `Direction`, `Distance`, `hit_type` | Árbol completo de outcomes | Además, `Distance` mide el **carry** directamente (F4.4) |

**Eliminado de v1:** RE24 (sin corredores), transformer secuencial (sin orden), causal forest (sin secuencia ni confusores clave), MILP de scouting (sin costos; reactivable si el club los da).

### 1.1 Decisiones del orquestador sobre D00 (datos reales de F0.0)

Dataset real: **635 002 lanzamientos · 2 127 juegos · 1 135 lanzadores · 865 bateadores · 2024–2026.** Las categorías reales tienen más valores que el diccionario del organizador. `docs/diccionario.csv` **no se edita** (es del organizador): la fuente de verdad de categorías reales es `config/categorias.yaml`, y cada decisión es un ADR.

Ninguna de estas decisiones usa outcomes: son inventarios de etiquetas y reglas de limpieza, y F1 (pre-registro) aún no ocurre. Por eso pueden fijarse ahora sin sesgo post hoc.

| ADR | Tema | Decisión | Por qué |
|---|---|---|---|
| **002** | `AutoPitchType` (12 valores) | Se conserva la etiqueta cruda y se agrega `familia`: **FF** = Four-Seam · **SI** = Sinker, TwoSeamFastBall, OneSeamFastBall · **FC** = Cutter · **SL** = Slider, Sweeper (con bandera `es_sweeper`) · **CU** = Curveball · **CH** = Changeup, Splitter · **EXC** = Knuckleball, Other, Undefined | Two-seam y one-seam son la misma familia física que el sinker (corrida al brazo + hundimiento). Sweeper es un slider de quiebre horizontal. Splitter y changeup engañan por diferencial de velocidad, que es justo el mecanismo de H2. El knuckleball casi no gira: la descomposición Magnus de F2 no aplica. Las formas de F5 (GMM) siguen siendo la representación principal ("shape over label"); la familia solo se usa para la recta primaria, H2 y reportes |
| **003** | Mano `Undefined` / `Switch` | **Lanzador:** imputar por la moda del lanzador si su participación ≥ 95 %; si no, por el signo de `RelSide`, solo si en las filas con mano definida el signo concuerda con la mano ≥ 99 % (el signo se aprende de los datos, no se supone); si no, descartar. **Bateador:** `Switch` → mano opuesta a la del lanzador; `Undefined` → moda del bateador si ≥ 95 %; si el bateador muestra ambos lados ≥ 5 % cada uno, opuesta al lanzador; si no, descartar | Un ambidiestro batea casi siempre del lado contrario al lanzador. El espejo de zurdos (F5.1) y el pelotón necesitan mano resuelta en cada lanzamiento |
| **004** | `PitchCall` | `FoulBall`, `FoulBallFieldable`, `FoulBallNotFieldable` → **`Foul`** (columna `pitch_call_h`; la cruda se conserva). `Undefined` se excluye de modelos y de la estimación de la cadena de conteos | Para la cadena y para N3 los tres son el mismo evento: foul sin out. Un foul atrapado es out y Trackman lo marca `InPlay`. I6 se reescribe: `is_contact ⇔ pitch_call_h ∈ {Foul, InPlay}` |
| **005** | `altitude_category` y "Harp Helú" | (a) **Nulos:** si la cubeta es constante dentro de cada juego (nueva identidad I9), se imputa por juego; si el juego entero es nulo, queda fuera de las pruebas confirmatorias y F2 le **predice** la cubeta desde $\hat\rho_g$ como validación 🔎. (b) **Composición:** con 2 127 juegos en 3 temporadas el dataset es de **toda la liga**, no solo de Diablos (que juega ~45 en casa por temporada). La cubeta *Extreme* mezcla varios parques sobre ~1 800 m. (c) **Definición operativa:** "Stuff+ en Harp Helú" = Stuff+ evaluado en $\rho_{CDMX}$, la moda de la clase de densidad más alta que F2 encuentre dentro de *Extreme* | CDMX (2 232 m, $\rho/\rho_0=0.762$) y Puebla (2 192 m, 0.766) tienen el mismo aire: ningún método físico los separa, y para la pregunta del reto da igual, porque lo que mueve el lanzamiento es ρ, no el nombre del estadio. Aguascalientes, Durango y León (~0.79–0.80) sí son separables con un error estándar por juego de ~0.01 en $\log\rho$ |
| **006** | `Outs = 3` (8 filas) | Se excluyen de modelos y de la cadena; se conservan para la suma de I7. Nueva identidad I10: `Outs ∈ {0,1,2}` | Son errores de captura; 8 de 635 002 no mueven nada, pero deben quedar contados |
| **007** | `play_result` (16 valores) | Evento terminal por prioridad: (1) `KorBB=Strikeout` → **K**; `KorBB=Walk` → **BB**; (2) `pitch_call_h=HitByPitch` → **HBP**; (3) `InPlay` + `play_result` ∈ Single/Double/Triple/HomeRun → **1B/2B/3B/HR**; Out o FieldersChoice → **OUT_BIP**; Error → **ROE**; Sacrifice → **SAC**. Cualquier otro valor → no terminal. Todo valor sin regla → discrepancia, no se adivina | En la regresión de pesos lineales (F4.1), ROE y SAC llevan su propio peso porque sí generan carreras; omitirlos sesgaría a los demás. Para valorar al **lanzador** (N5) un error cuenta como out: es responsabilidad de la defensa |

**Consecuencias en el resto del roadmap** (ya aplicadas abajo): F0 implementa ADR-002 a 007, I9 e I10, y el sintético reproduce cada caso real con una prueba. La normalización y la compuerta G2.2 de F2 cambian. H2 usa las familias de ADR-002. La recta primaria de F5.3 usa familias. Los ADR que el roadmap pedía en F4 y F6 pasan a ser 008 y 009.

### 1.2 Decisiones del orquestador sobre la corrida real de F0

Fallaron G0.1, G0.2 y G0.3. Ninguna falla es un error de código: las tres son supuestos del roadmap que el dato real no cumple. Son reglas de **control de calidad de datos**, no hipótesis, y F1 aún no ocurre; por eso se redefinen aquí con su justificación, sin sesgo post hoc.

| ADR | Falla | Diagnóstico | Decisión |
|---|---|---|---|
| **010** | G0.2: I3 = 0 % (razones $2c_2/a_0$: X −1.87, Y −1.00, Z 0.17) | Y da −1.00 casi exacto: el eje Y del polinomio corre en sentido opuesto al `y` de los 9P. X y Z no dan ±1: **los ejes del polinomio no son los mismos que los de los 9P**, no es un problema de origen de tiempo (un desplazamiento de tiempo no cambia $c_2$) | **La trayectoria canónica es la de los 9P**: $\mathbf r(t)=\mathbf r_0+\mathbf v_0t+\tfrac12\mathbf a t^2$. Es exactamente el mismo modelo de aceleración constante, con convención ya conocida. F0 identifica el mapeo de los polinomios por una **matriz 3×3** de regresiones ($c_2^{P}$ sobre $a_{0}^{q}$, $c_1^{P}$ sobre $v_0^{q}$) y busca la permutación con signo que dé $R^2\ge0.99$. Si existe, se documenta y los polinomios sirven de verificación cruzada. Si no, se declaran no canónicos y no se usan. **Ninguna fase depende de ellos** |
| **011** | G0.1: I6′ = 99.75 % (suma 99.93 %; contacto ⇔ Foul/InPlay 99.75 %; whiff ⇒ StrikeSwinging 100 %) | Las banderas `is_*` del organizador no son partición exacta de `PitchCall` en ~0.25 % de los lanzamientos (probablemente foul tips y fouls atrapables marcados distinto). `is_hit_by_pitch` es siempre 0 | **El árbol de desenlaces se define desde `pitch_call_h`**, no desde las banderas: swing = {StrikeSwinging, Foul, InPlay}; whiff = StrikeSwinging; contacto = {Foul, InPlay}. Así es una partición exacta por construcción. Las `is_*` quedan como verificación cruzada con su tabla de discrepancias. En el conteo manda `evento_terminal` (ADR-007) sobre `pitch_call_h`: un foul con `KorBB=Strikeout` es K |
| **012** | G0.3: I7 = 86.1 % (outs por media entrada: 3 → 31 883; **2 → 4 763**; 0–1 → 276; ≥4 → 101) | 12.9 % terminan con 2 outs y apenas 0.5 pp se explican por la última media entrada del juego. Candidatos: tercer out en evento sin lanzamiento propio (robo, pickoff), lanzamientos faltantes de Trackman, o `OutsOnPlay` que no cuenta outs de corredores | Dos criterios de completitud. **A (estricto):** suma de outs = 3. **B (amplio):** el estado previo `Outs = 2` aparece en la media entrada y existe la media entrada siguiente del juego. F4.1 usa **A** como principal y **B** como sensibilidad; si los pesos difieren más que sus IC, se escala. Las medias entradas con ≥ 4 outs son inconsistentes y se excluyen de ambos |
| **013** | IDs nulos: `pitcher_anon_id` 3 272 (0.52 %), `batter_anon_id` 2 020, `catcher_anon_id` 2 325 | Un ID nulo de lanzador formaría un "lanzador fantasma" en `GroupKFold` y en los rasgos de arsenal | Dos banderas separadas. `excluir_modelo`: lo de ADR-002/003/004/006 **más** `pitcher_anon_id` nulo. `excluir_cadena`: solo `pitch_call_h = Undefined`, `Outs` inválido y `play_result=NeutralPlay` con `InPlay` (7 filas sin resultado). La cadena de conteos y los pesos lineales usan **todas** las transiciones válidas, porque la mano o el ID no afectan a la transición del conteo |

**Buenas noticias de la corrida:** 765 lanzadores tienen ≥ 30 lanzamientos en ≥ 2 cubetas y 665 aparecen en las tres. La identificación intra-lanzador de F2, F3 y H1 tiene muestra de sobra. I9 = 100 %: la cubeta es constante por juego. Cero valores sin regla. Exclusiones totales 0.33 % (≈ 0.85 % con ADR-013).

**Nota para F7:** 2026 trae 135 604 lanzamientos, ~55 % de una temporada completa. El *season holdout* debe reportar el tamaño de cada pliegue y no comparar métricas sin esa nota.

### 1.3 Decisiones del orquestador sobre la segunda corrida de F0

**Hallazgo 1 — los polinomios sí son los 9P (corrige ADR-010).** La regresión conjunta da $R^2=1.000000$ con coeficientes exactamente $0.5000$: $c_2^X=\tfrac12a_{y0}$, $c_2^Y=\tfrac12a_{z0}$, $c_2^Z=\tfrac12a_{x0}$. Es una **permutación exacta** (X→y, Y→z, Z→x, signos +). La regla de v2.4 la rechazó porque comparó $c_1$ con $\mathbf v_0$ sin tiempo: si el polinomio empieza en otro instante $t_s$, entonces

$$c_1=\mathbf v_0+\mathbf a\,t_s,\qquad c_0=\mathbf r_0+\mathbf v_0t_s+\tfrac12\mathbf a\,t_s^2,$$

y $c_1$ ya no encaja con $\mathbf v_0$ solo. El eje con más curvatura (vertical) pierde más $R^2$, que es justo lo observado (0.989). Con el intercepto del eje X, $t_s\approx-0.69/27\approx-0.026$ s: unos 3.5 ft antes de $y_0=50$ ft, es decir, **el polinomio arranca en la liberación** (~54 ft).

**Hallazgo 2 — el `ZoneTime` se mide desde la liberación (ADR-014).** La verificación de v2.4 evaluó los 9P en $t=$`ZoneTime`, pero el reloj de los 9P empieza en $y_0=50$ ft. Con $t_s\approx-0.026$ s, el error esperado en $y$ es $|v_y|\,|t_s|\approx135\times0.026\approx3.5$ ft. Se observaron 4.27 ft de mediana: el mismo orden. El error de 1.29 ft en `PlateLocSide` es demasiado grande para venir solo del tiempo ($|v_x|\,|t_s|\approx0.15$ ft): apunta a un **signo invertido** entre $x$ y `PlateLocSide`.

| ADR | Decisión |
|---|---|
| **010 (enmienda)** | Los polinomios son los 9P en ejes permutados (X→y, Y→z, Z→x) con origen de tiempo en la liberación. Se reclasifican de `no_canonicos` a **`equivalentes`**. La trayectoria canónica sigue siendo 9P; el polinomio da $t_s$ por lanzamiento: $t_{s,i}=(c^X_{1,i}-v_{y0,i})/a_{y0,i}$ |
| **014** | **Marco temporal único.** El tiempo al plato **no** es `ZoneTime`: es la raíz de $y(t_p)=y_p$ con la trayectoria 9P. El plano $y_p\in\{17/12,\ 0\}$ ft y el signo $s\in\{+1,-1\}$ en `PlateLocSide` $=s\,x(t_p)$ se eligen por mínimo error contra `PlateLoc*`. Verificación cruzada: `ZoneTime` $\approx t_p-t_s$. La Prop. 1 usa $t_m=\tfrac12(t_s+t_p)$, el punto medio entre liberación y plato |

> ⚠️ **Corregido en §1.4 (v2.6).** La lectura MNAR de este hallazgo ("se pierden más los ponches") y el estimador $\hat\pi_K$ por déficits **no están identificados** (D01). La Prop. 15 queda condicionada a G0.9.

**Hallazgo 3 — los outs que faltan son turnos finales perdidos, no robos (ADR-015).** De las 4 763 medias entradas con 2 outs, solo el 9.5 % deja un turno incompleto (lo que dejaría un robo o un pickoff con 2 outs). El 90 % restante pierde **el último turno completo**: todos sus lanzamientos faltan. Además, comparadas con las de 3 outs, tienen **0.525 ponches menos** por media entrada y solo 0.388 outs en juego menos. Si los turnos perdidos fueran un final al azar, la mayoría serían outs en juego.

*Consecuencia:* los ponches que terminan la entrada se pierden con mucha más frecuencia que los outs en juego. Es **falta no aleatoria** (MNAR), y sesga hacia abajo $P(K\mid 2\text{ strikes})$ y con ello $V(c)$. Con la cuenta gruesa por déficits, la fracción de ponches entre los turnos perdidos es

$$\hat\pi_K=\frac{0.525}{0.525+0.388+0.026}\approx0.56 .$$

**Corrección por ponderación inversa (Horvitz–Thompson).** Sea $M$ el número de turnos finales perdidos, y $n_K$ y $n_B$ los turnos finales registrados que terminan en ponche o en out en juego (estado previo `Outs=2`). Cada lanzamiento de un turno final de tipo $\tau$ recibe peso

$$\omega_K=\frac{n_K+\pi M}{n_K},\qquad \omega_B=\frac{n_B+(1-\pi)M}{n_B}.$$

**Proposición 15 (insesgamiento y cotas).** Si, dado su tipo, que un turno final se pierda es independiente de sus lanzamientos, los conteos ponderados de transiciones son insesgados para los conteos completos cuando $\pi$ es el verdadero. Como $\pi$ solo se estima de forma gruesa, se calculan $V(c)$ y todo lo que depende de él con $\pi\in\{0,\hat\pi_K,1\}$: los extremos son **cotas** (estilo Manski) que no necesitan ningún supuesto sobre $\pi$.

*Demostración.* $\mathbb E[\sum_i\omega_{\tau(i)}\mathbb 1_i]=\sum_\tau\omega_\tau\,n_\tau\,\bar{\mathbb 1}_\tau=\sum_\tau(n_\tau+M_\tau)\,\bar{\mathbb 1}_\tau$, con $M_K=\pi M$, porque bajo el supuesto los perdidos de tipo $\tau$ tienen la misma distribución de transiciones que los registrados. $V(c)$ es monótono en la masa de K, así que los extremos de $\pi$ acotan su valor. ∎

**Lo que se verifica ahora en F0:** la tasa de medias entradas de 2 outs **por cubeta y año**. Si difiere entre cubetas, la pérdida de datos se confunde con la altitud en cualquier comparación de outcomes entre cubetas (F8). Es la amenaza más seria que ha aparecido hasta ahora.

---

### 1.4 Decisiones del orquestador sobre la tercera corrida de F0

**Cerrado.** G0.1–G0.7 ✅.

- **ADR-010 enmendado.** La permutación X→y, Y→z, Z→x es exacta ($R^2=1.000000$, coeficientes $0.5000$). $c_1$ con $t_s$ da $R^2=1.000000$ en los tres ejes.
- **Origen del polinomio.** Mediana $t_s=-0.0363$ s, que con $|v_y|\approx130$ ft/s pone el origen en $y\approx54.7$ ft: la liberación, con extensión de ~6 ft. La cifra $-0.026$ s de §1.3 era una estimación gruesa.
- **ADR-014.** $y_p=17/12$ ft, $s=-1$. Error mediano/p99: `PlateLocSide` 0.0017/0.0091 ft y `PlateLocHeight` 0.0013/0.0318 ft. $|\text{ZoneTime}-(t_p-t_s)|$ tiene mediana 0.03 ms. Queda fijo en `config/default.yaml`; la Prop. 1 de F2 usa $t_m=\tfrac12(t_s+t_p)$ por lanzamiento.

**Hallazgo 4 — los outs faltantes son, sobre todo, outs que `OutsOnPlay` no cuenta.** G0.8 falló: la tasa de medias entradas no finales con 2 outs registrados y sin turno incompleto es 9.87 / 11.71 / 14.27 % (No / Medium / Extreme). El rango es 4.40 pp, estable en los tres años. La clasificación "turno final perdido" suponía que `OutsOnPlay` cuenta todos los outs. El dato real contradice ese supuesto en cinco puntos:

1. **Casi no hay jugadas de 2 outs.** Solo ~280 jugadas tienen `OutsOnPlay ≥ 2` (217 son OUT_BIP). A la tasa de MLB 2023 (132 dobles matanzas por equipo en 162 juegos; Wikipedia, *Double play*) se esperan ≈ 1.63 por juego, ≈ 3 470 en 2 127 juegos. Si es así, ~92 % de las dobles matanzas se registran como 1 out.
2. **El out de los ponches está impuesto.** `OutsOnPlay = 1` en el **100 %** de los 30 648 K. No aparece ningún tercer strike caído (0 outs) ni ningún K + robo atrapado (2 outs). El campo se asigna, no se registra.
3. **Los conteos por juego siguen una Poisson.** La media es $\lambda=1.897$ por juego. Poisson predice $P(\ge1)=0.850$ y $P(>2)=0.296$; se observaron 0.847 y 0.299, con dispersión $\varphi=1.10$. Es la firma de un evento de juego a tasa constante. Una falla del sensor u operador se concentraría en algunos juegos ($\varphi\gg1$).
4. **La composición de las medias entradas de 2 outs encaja con la doble matanza.** Con doble matanza solo hay 2 turnos de out y uno es un rodado. Eso predice K ≈ 0.30–0.37 y OUT_BIP ≈ 1.6 por media entrada; se observaron 0.374 y 1.579. Tienen **más** BB (0.542 vs 0.41), HBP y ROE pese a tener menos turnos, porque una doble matanza exige corredores. Con pérdida de un turno independiente de los demás, los K por out registrado deberían quedar en ≈ 0.30 (D01); se observó 0.187.
5. **El gradiente tiene explicación física.** En altura hay más corredores, luego más oportunidades de doble matanza.

**Dos mecanismos.** Por regla, toda media entrada no final tiene 3 outs reales. Una media entrada con 2 outs registrados y todos sus turnos terminados viene de uno de estos:

- **U — out no contabilizado.** Están todos los lanzamientos, pero un out real no está en `OutsOnPlay`: doble matanza registrada como 1, K + robo atrapado, pickoff, o corredor puesto out entre lanzamientos.
- **L — turno perdido.** Faltan todos los lanzamientos de un turno que terminó en out.

U **no sesga** ningún outcome por lanzamiento: no falta nada. L sí, y es lo que G0.8 quería medir. La v2.5 midió U + L juntos.

#### Proposición 16 (identificación de la pérdida real)

**Definiciones.**

- $T$ = medias entradas no finales, `Inning` ≤ 9, consistentes (outs registrados ≤ 3) y sin turno incompleto.
- $O_h=\sum$ `OutsOnPlay` y $P=\{h\in T:O_h=2\}$.
- $N_h$ = número de turnos de $h$ con `evento_terminal` ∈ {1B, 2B, 3B, BB, HBP, ROE}, y $Z_h=\mathbb 1[N_h=0]$.
- Por cubeta $b$: $f_b=P(Z=1\mid b)$ en $T_b$, $p^0_b=P(h\in P,\,Z=1\mid b)$ y $r_b=P(L\mid b)$.

**Supuestos.**

- **(S1)** U exige un corredor en base. En entradas ≤ 9 no hay corredor colocado, y todo corredor proviene de un turno que llegó a base en la misma media entrada, así que $P(Z=1\mid U)=0$.
- **(S2)** L elimina un turno de **out**, lo que no cambia $N_h$. Además, dentro de cada cubeta, la pérdida es independiente de $Z$.

**Resultado.** Bajo S1 y S2,

$$r_b=\frac{p^0_b}{f_b},\qquad \theta_b=\frac{r_b}{P(h\in P\mid b)}\ \ (\text{fracción de }P\text{ que es pérdida real}).$$

*Demostración.*

1. U y L son disjuntos dentro de $P$: si ocurrieran juntos, $O_h=1$ y la media entrada no estaría en $P$.
2. Por lo tanto $P(Z=1,P\mid b)=P(Z=1,U\mid b)+P(Z=1\mid L,b)\,P(L\mid b)=0+f_b\,r_b$, usando S1 y S2.
3. $f_b$ es identificable, porque ni U ni L alteran el $Z$ observado: U no quita turnos, y L quita un turno de out.

∎

*Sesgos residuales.*

- Un tercer strike caído o una interferencia del cátcher pone corredor con $N_h=0$, de modo que U tendría $P(Z=1\mid U)>0$ pequeño. Eso sesga $\hat r_b$ hacia arriba, en dirección conservadora.
- Perder un turno que llegó a base sin outs puede convertir $Z$ de 0 a 1 en entradas de 3 outs; el efecto es de segundo orden.
- Si S2 falla porque la pérdida es más probable en entradas dominantes, $\hat r_b$ sobreestima (conservador). Si es más probable en entradas largas, subestima. Por eso las compuertas usan un **parámetro de sensibilidad** $\Gamma=P(Z=1\mid L,b)/f_b\in[\tfrac12,2]$, al estilo Rosenbaum (2002), y se evalúan con $\Gamma\hat r_b$, $\Gamma=2$.

#### Proposición 17 (cota del sesgo en contrastes entre cubetas)

**Definiciones.**

- Sea $Y$ un outcome binario por turno; el peor caso es $Y$ = K, porque solo un turno de out puede ser K.
- $\tilde m_b$ = turnos observados por media entrada de $T_b$.
- $\tilde\kappa_b$ = tasa observada.
- Fracción desconocida $\pi_b\in[0,1]$ de los turnos perdidos con $Y=1$.

**Resultado.** La tasa real es

$$\kappa_b=\frac{\tilde\kappa_b\tilde m_b+\pi_br_b}{\tilde m_b+r_b},$$

que recorre un intervalo de ancho $r_b/(\tilde m_b+r_b)$ cuando $\pi_b$ recorre $[0,1]$. El conjunto identificado del contraste Extreme − No mide

$$W(\Gamma)=\sum_{b\in\{\text{Ext},\text{No}\}}\frac{\Gamma\hat r_b}{\tilde m_b+\Gamma\hat r_b}.$$

*Demostración.* Cotas de peor caso de Manski (1990): la tasa es lineal y monótona en $\pi_b$, y las cubetas son independientes. ∎

**Referencia de precisión.** $\mathrm{SE}_{ref}=\sqrt{\bar\kappa(1-\bar\kappa)(1/n_{Ext}+1/n_{No})}$, donde:

- $\bar\kappa$ = tasa global de K por turno: una sola cifra, no por cubeta.
- $n_b$ = turnos de la cubeta.

Ignora el agrupamiento por juego, así que el SE sale **menor** y la regla es más estricta.

**Por qué el umbral $3.92\,\mathrm{SE}_{ref}$.** Si el ancho del conjunto identificado supera el ancho del IC95 muestral ($2\times1.96\,\mathrm{SE}$), la incertidumbre de identificación domina a la de muestreo y el contraste deja de ser informativo (Imbens y Manski, 2004).

#### Reglas de decisión (fijadas antes de la corrida; no se ajustan después)

| Compuerta | Regla |
|---|---|
| **G0.9** (mecanismo) | $\hat\theta$ global con IC95 por bootstrap de juegos. **U dominante** si IC95 sup ≤ 0.25 · **L dominante** si IC95 inf ≥ 0.50 · **mezcla** en otro caso. Se reporta siempre: no falla. |
| **G0.8′** (sustituye a G0.8) | $W(\Gamma{=}2)\le3.92\,\mathrm{SE}_{ref}$. Si pasa y además $W(\Gamma{=}2)\le\mathrm{SE}_{ref}$ → `perdida_ignorable: true`. Si pasa sin eso → `false`, y F8 reporta los contrastes de outcomes con intervalo de Imbens–Manski. **Si falla → discrepancia, no se sigue a F1.** |

**Consecuencias por escenario**

| G0.9 | Pesos ω de ADR-015 (Prop. 15) | F4.1 pesos lineales | F4.2 cadena | G4.6 / G6.5 |
|---|---|---|---|---|
| U dominante | **Retirados**: no falta ningún lanzamiento, y ω inventaría ponches | **C principal** (todas las de $T$ más regresor $u_h=3-O_h$, con $w_u\le0$, el valor de un out no contado); A como sensibilidad, porque A excluye las entradas con doble matanza y selecciona contra el tráfico, distinto por cubeta | sin pesos | G4.6 = solo A vs C; G6.5 retirada |
| mezcla o L dominante | ω **por cubeta** con $M_b=\hat r_b\lvert T_b\rvert$ y $\pi\in\{0,1\}$ (cotas); **sin** $\hat\pi_K$ | A principal, C sensibilidad (v2.5) | con ω, $\pi\in\{0,1\}$ | vigentes |

| ADR | Decisión |
|---|---|
| **016** | **Outs no contabilizados.** `OutsOnPlay` no es un registro fiel de outs: es constante en K y casi nunca vale 2. La media entrada con 2 outs registrados y sin turno incompleto se llama "out faltante" (no "turno final perdido"), y se descompone en U y L con la Prop. 16. G0.8 se sustituye por G0.8′ (Prop. 17). Se acepta D01: $\hat\pi_K$ por déficits no está identificado y se retira. *Transparencia de pre-registro:* los diagnósticos usan tráfico de corredores por cubeta, que no es estadístico de ninguna H1–H6. H3 condiciona en EV×LA y usa valor de batazo. |

---

### 1.5 Cierre de F0 (tag `fase00`) y decisiones para F1–F5

**Veredicto.** G0.1–G0.9 ✅ con datos reales. La predicción de §1.4 se confirmó: $\hat\theta=0.074$ [0.059, 0.090] → **U dominante**. Corroboraciones:

- Rodados entre los OUT_BIP con < 2 outs: 72.8 % en P contra 45.0 % en $T\setminus P$.
- Hueco en la columna `Outs`: 36.0 % en P contra 0.4 %.
- $|P|$ por juego: Poisson con $\varphi=1.00$.
- Jugadas con `OutsOnPlay` ≥ 2: el 8 % de las dobles matanzas esperadas.
- $\hat r_b$: 0.99 / 0.73 / 0.92 % (Extreme / Medium / No), sin gradiente.

**Configuración vigente:** `qa.mecanismo_outs = U` y `qa.perdida_ignorable = false`, porque $W(\Gamma{=}2)/\mathrm{SE}_{ref}=3.55$. Quedan activas las consecuencias de §1.4 para U:

- se retiran los pesos ω;
- F4.1 usa el modelo C como principal;
- F4.2 va sin pesos;
- G6.5 queda retirada;
- F8 reporta los contrastes de outcomes con Imbens–Manski.

**🔎 Gradiente residual de P.** El OR de Extreme vs. No pasa de 1.51 a 1.43 al controlar por $N_h$. $N_h$ cuenta corredores, no oportunidades de doble matanza (corredor en 1B con < 2 outs), ni la tasa de rodados, ni la práctica de registro de cada operador. No afecta ningún outcome por lanzamiento, porque U no quita lanzamientos. *Consecuencia:* en F4.1 el peso de $u_h$ lleva desviación por cubeta, $w_u+\gamma_u^{(b)}$ con ridge, porque mezcla el valor real de la doble matanza con la práctica de registro.

**🔎 I8, Cutter.** `HorzBreak` medio −0.39 in (D) y −1.13 in (Z): mismo signo. Hipótesis: un desfase lateral común $\delta_x$ (calibración o eje) que solo domina cuando el movimiento horizontal verdadero es ≈ 0. Se prueba en F5.1:

- $\hat\delta_x=\operatorname{mediana}_k\tfrac12(\overline{HB}_{k,D}+\overline{HB}_{k,Z})$ sobre los tipos $k$, con IC95 por bootstrap de lanzadores.
- Si el IC excluye 0 y $|\hat\delta_x|\ge0.5$ in, el espejo de zurdos es la reflexión $x\mapsto2\hat\delta_x-x$ (sobre $\delta_x$, no sobre 0) en las componentes horizontales afectadas.
- Si no, el cutter es asimétrico por mano y se reporta como 🔎.

**Transparencia del pre-registro.** Antes de F1 ya se vieron, por cubeta:

- el alcance;
- $f_b$ = % de medias entradas sin corredores (24.9 / 26.4 / 31.8 %);
- la tasa de P;
- los OR del logit.

Ninguna es estadístico de H1–H6, y se declaran en `docs/HIPOTESIS.md`.

---

### 1.6 Revisión del diseño de F2 (D02a del orquestador)

**(1) Prop. 3′ — sesgo de calibración (sustituye a la Prop. 3).** Con escala espacial $\lambda_g$ y reloj $\tau_g$ por parque, se mide $\tilde{\mathbf v}=(\lambda/\tau)\mathbf v$ y $\tilde{\mathbf a}=(\lambda/\tau^2)\mathbf a$. Al restar la gravedad verdadera,

$$\tilde{\mathbf a}-\mathbf g=\frac{\lambda}{\tau^2}\,\mathbf a_{aero}+c_g\,\mathbf g,\qquad c_g=\frac{\lambda_g}{\tau_g^2}-1 .$$

*Consecuencias:*

- (a) El cociente aerodinámico $\mathbf a_{aero}/\lVert\mathbf v\rVert^2$ escala por $1/\lambda$, de modo que $\delta^D_g=\log\rho_g-\log\lambda_g$; el reloj no entra.
- (b) Escala **y** reloj dejan el mismo residuo $c_g\mathbf g$, casi perpendicular a $\mathbf v$. Ese residuo carga en el canal de sustentación, así que $\delta^L_g-\delta^D_g$ estima $c_g$, la combinación, sin poder separar escala de reloj.
- (c) Un sesgo de 2 % mueve $\delta$ un 2 %, un orden de magnitud bajo la señal ($|\log0.762|=0.27$).

*Detector adicional.* Si `SpinAxis` es medido (no inferido del movimiento), sea $\hat{\mathbf e}=\hat{\mathbf v}\times\hat{\mathbf n}_{spin}$. El modelo es $\tilde{\mathbf a}\cdot\hat{\mathbf e}_i=c_g(\mathbf g\cdot\hat{\mathbf e}_i)+\beta_{j,k}+\epsilon_i$, donde $\beta_{j,k}$ absorbe la estela por costuras y el desajuste de eje del lanzador; de ahí sale $\hat c_g$ por juego. Si la varianza de $\tilde{\mathbf a}\cdot\hat{\mathbf e}$ es ≈ 0, el eje es inferido del movimiento: se declara así y el único detector es G2.3.

**(2) Prop. 2′ — dos efectos fijos (sustituye a la Prop. 2).**

$$y^D_i=\delta_{g(i)}+\alpha_{j(i),k(i)}+f_D(S_i,k_i,h_i,\text{year})+\eta_i .$$

$\delta_g-\delta_{g'}$ está identificado dentro del **conjunto conectado** del grafo bipartito juegos–(lanzador×forma) (Abowd, Kramarz y Margolis, 1999); se reporta su tamaño. *Por qué:* sin $\alpha$, el C_D medio del staff local carga en el parque, con un sesgo de orden 0.01 en $\log\rho$, igual a la resolución que pide G2.2(c). Se estima por proyecciones alternadas (Guimarães y Portugal, 2010). La normalización $\bar\delta_{No}:=0$ no cambia.

**(3) Errores estándar.**

- Para $\delta_g$: corrección CR2 (Bell y McCaffrey, 2002) con conglomerados = lanzador dentro del juego, porque hay pocos (~9 por juego).
- Para contrastes de medias por cubeta y la regresión de Deming: agrupamiento doble juego × lanzador (Cameron, Gelbach y Miller, 2011).
- G2.4 usa la mediana del SE CR2.

**(4) Error del punto medio.** $\varepsilon\approx s^2/4$ con $s\propto\rho$: depende de ρ, no lo absorbe $f_D$. El sesgo diferencial es ≈ $s_0^2(1-0.76^2)/4\approx0.001$ en $\log\rho$, despreciable; la sintética lo verifica.

**(5) Fallback del soporte común.** Nunca se elimina `year`, porque la pelota cambia de arrastre entre temporadas. El orden es: menos nudos → lineal → fundir forma en familia → marcar el juego como baja confianza.

**(6) Sintética de F2, además de lo ya diseñado:**

- efecto de lanzador $\alpha_{j}$ con desviación estándar 0.05 en log C_D, y staffs asignados a parques locales: debe mostrar el sesgo sin $\alpha$ y su desaparición con $\alpha$;
- casos (λ = 1.02, τ = 1) y (λ = 1, τ = 1.01): ambos deben detectarse en G2.3 con $\hat c_g$ ≈ ±0.02.

---

## 2. Notación y constantes

Ejes Trackman: origen en la punta del plato, $y$ hacia el montículo, $z$ hacia arriba. Índices: lanzamiento $i$, juego $g$, lanzador $j$, tipo/forma $k$, cubeta $b(g)$, conteo $c=(B,S)$, mano $h$.

| Símbolo | Valor | Nota |
|---|---|---|
| $m$ | 0.145 kg | 5.125 oz |
| $r$, $A=\pi r^2$ | 0.0368 m, 4.26×10⁻³ m² | circunferencia 9.125 in |
| $g$ | 32.174 ft/s² | |
| $\kappa(\rho)$ | $\rho A/(2m)$ | |
| $S$ | $r\omega/\lVert\mathbf v\rVert$ | factor de giro |

**Densidad barométrica** (misma temperatura que la referencia):

$$\frac{\rho(h)}{\rho_0}\approx\left(1-2.25577\times10^{-5}\,h\right)^{5.25588}$$

| Altitud | $\rho/\rho_0$ | $\log(\rho/\rho_0)$ | 18" de break se vuelven |
|---|---|---|---|
| 3 m (Campeche) | 1.000 | 0.000 | 18.0" |
| 532 m (Monterrey) | 0.939 | −0.064 | 16.9" |
| 1565 m (Saltillo) | 0.828 | −0.189 | 14.9" |
| 1609 m (Denver) | 0.823 | −0.194 | 14.8" ← Nathan: 14–15" ✓ |
| 1921 m (Aguascalientes) | 0.792 | −0.233 | 14.3" |
| 2232 m (Harp Helú) | **0.762** | **−0.272** | **13.7"** |

La columna derecha usa la Proposición 4 (escalamiento lineal). Que reproduzca el número de Nathan para Denver es la primera validación del marco.

---

## 3. Grafo de fases

```
F0.0 Inspección ─► F0 Infra+QA ─► F1 Pre-registro ─► F2 Densidad por juego ─► F3 Invariantes + operador T
                                                                   │
                                          ┌────────────────────────┴───────────┐
                                          ▼                                    ▼
                                   F4 Variable objetivo                F5 Arsenal + fugas
                                          └────────────────┬───────────────────┘
                                                           ▼
                                                    F6 Modelos ─► F7 Validación ─► F8 Efecto altitud + H1–H6
                                                                                          │
                                                       F11 Reporte ◄─ F10 Dashboard ◄─ F9 Agregación + perfil ideal
```

F4 y F5 son independientes entre sí: se pueden correr en paralelo en dos sesiones de Claude Code.

---

## 4. Fases

> **Todo prompt de esta sección se pega con el sufijo §0.3 al final.** Después de la corrida local se usa el prompt de revisión §0.4 con el modelo que indique la fase (Opus si la fase tiene auditoría, si no Sonnet).

### F0.0 — Andamiaje, generador sintético e inspección de los datos crudos

**Modelo:** Sonnet · **Duración:** 2–3 h (nube) + 15 min (local)

**Objetivo.** Dejar el repositorio listo para todo el proyecto y, en la primera corrida local, confirmar que `stuff_model_df.parquet`, `stuff_model_df.pkl` y `stuff_model_df.rds` son **el mismo dataset**, elegir la fuente canónica y verificar el diccionario.

**Por qué el parquet es la fuente canónica por defecto:**

| Formato | Lectura | Riesgo |
|---|---|---|
| `.parquet` | perezosa (`polars.scan_parquet`), columnar, tipos explícitos | ninguno |
| `.pkl` | carga completa con pandas | **`pickle` ejecuta código al cargar** (aceptable solo porque viene del organizador); depende de la versión de pandas que lo creó |
| `.rds` | carga completa con `pyreadr` | factores de R → categóricas; `NA` → nulos; fechas como días desde 1970 |

**Matemática: criterio de equivalencia.** Con $D_1,D_2,D_3$ ordenados por `PitchUID`, son equivalentes si:

1. `PitchUID` es único en cada uno y $U_1=U_2=U_3$.
2. Mismas columnas (como conjunto) y mismo número de filas.
3. Numéricas: $\max_i|X^{(a)}_i-X^{(b)}_i|\le10^{-9}\max(1,|X^{(a)}_i|)$, con nulos en las mismas posiciones.
4. Categóricas y texto: igualdad exacta tras normalizar a string y homologar nulos (`NA`, `None`, `NaN`, `""`).

Costo $O(n\log n)$; se compara **por columnas** y un archivo a la vez, así alcanza con 32 GB.

**El generador sintético es la pieza que hace posible trabajar sin datos.** Produce un dataset con **todas** las columnas del diccionario, los mismos tipos y categorías, y que cumple por construcción las identidades I1–I8 de F0. En F2 se le agrega física exacta con ρ conocida por cubeta. Cada fase se prueba primero contra él.

**Prompt (Sonnet):**

```text
Lee CLAUDE.md y ROADMAP.md §0, §1, §2 y §4-F0.0.

1. Andamiaje: pyproject.toml (paquete "pitcheo", Python 3.12, gestionado con uv) con
   dependencias polars, pyarrow, pandas, pyreadr, numpy, scipy, scikit-learn,
   lightgbm, statsmodels, matplotlib, streamlit, pyyaml; extra dev: pytest, ruff.
   CLI `pitcheo` con un subcomando por fase (f00_0, f00, f01 ... f11), como `dtcoach`
   en Historia-de-un-entrenador. Estructura: src/pitcheo/{cli,config,io,sintetico,qa,
   fisica,operador,objetivo,arsenal,modelos,validacion,altitud,agregacion,
   optimizacion}.py, tests/, scripts/fases/, app/, config/default.yaml,
   docs/{HIPOTESIS,DECISIONES,MODELO_MATEMATICO}.md, docs/discrepancias/,
   reports/{logs,privado}/. Agrega reports/privado/ al .gitignore.
2. src/pitcheo/sintetico.py: generar(n_juegos, semilla) → DataFrame con TODAS las
   columnas de docs/diccionario.csv, tipos y categorías del diccionario, ids
   anónimos con su formato (game_######, pitcher_#####...), cubetas de altitud,
   medias entradas completas (OutsOnPlay suma 3), conteos coherentes con PitchCall,
   flags is_* coherentes, y valores que cumplan I1–I8 de ROADMAP F0. Función
   escribir_tres_formatos(df, ruta) que escribe .parquet, .pkl y .rds (pyreadr).
3. src/pitcheo/io.py: lector perezoso del parquet canónico, lectores de .pkl y .rds,
   y comparar_formatos() con el criterio 1–4 de ROADMAP F0.0, por columna, un
   archivo en memoria a la vez.
4. `pitcheo f00_0`: tamaños en disco; equivalencia por columna (igual / distinta con
   nº de diferencias / ausente); perfil del parquet contra docs/diccionario.csv
   (presencia, tipo, % nulos, rango o hasta 50 valores únicos, cumplimiento de
   unit_or_values, columnas no documentadas); conteos de filas, PitchUID únicos,
   juegos, lanzadores, bateadores, year y altitude_category. Si el .pkl falla por
   versión de pandas, se reporta y se sigue.
5. Pruebas: el generador cumple el diccionario; comparar_formatos detecta
   diferencias sembradas (una celda alterada, una columna faltante, un ID duplicado).
6. scripts/fases/f00_0.sh según el sufijo §0.3; además, la primera vez, crea el
   entorno con `uv sync --extra dev`. README con "Cómo correr" al estilo de
   Historia-de-un-entrenador.
Compuertas (las evalúa el reporte con datos reales): G00.1 PitchUID único y mismos
IDs en los tres archivos; G00.2 equivalencia 2–4 en todas las columnas; G00.3 toda
columna del diccionario presente en el parquet. Si alguna falla, el reporte lo dice y
el orquestador elige la fuente: el código NUNCA elige por su cuenta.
```
*(+ sufijo §0.3)*

**Salidas:** paquete instalable, generador sintético, `reports/FASE_00_0.md`.

---

### F0 — Ingesta y QA por identidades

**Modelo:** Sonnet · **Duración:** 2 h (nube) + 15 min (local)

**Objetivo.** Datos canónicos tipados y verificación de que el dataset es internamente coherente *antes* de modelar nada.

**Matemática: identidades que el dato debe cumplir.** Cada una es una prueba sobre datos reales.

| ID | Identidad | Tolerancia |
|---|---|---|
| I1 | `SpeedDrop = RelSpeed − ZoneSpeed` | 0.05 mph |
| I2 | `count = f(Balls, Strikes)` | exacta |
| I3 | $2\,c_2^{(x,y,z)} = a_0^{(x,y,z)}$ si el polinomio está en $t$ con aceleración constante | 1 % |
| I4 | `VertBreak − InducedVertBreak` ≈ caída por gravedad $\tfrac12 g t_f^2$ (en pulgadas) | pendiente ∈ [0.95, 1.05] |
| I5 | `Tilt` ↔ `SpinAxis` biyectivos (correlación circular) | > 0.99 |
| I6 | `is_swing = is_whiff + is_contact`; `is_whiff ⇒ PitchCall=StrikeSwinging` | exacta |
| I7 | $\sum$`OutsOnPlay` por media entrada $=3$ en entradas completas | ≥ 90 % de medias entradas |
| I8 | Signo de `HorzBreak` se invierte con `PitcherThrows` para el mismo `AutoPitchType` | — |

Si I3 falla, la convención de tiempo del polinomio es distinta a la supuesta: se documenta, no se fuerza.

**Alcance del dataset** (crítico para la identificación): partidos, lanzadores y lanzamientos por `year × altitude_category`; lanzadores que aparecen en ≥2 cubetas (identificación intra-lanzador); juegos por cubeta y temporada. La hipótesis "solo Diablos" queda descartada por el número de juegos (ADR-005).

**Identidades nuevas (ADR-004 a 006):**

| ID | Identidad | Tolerancia |
|---|---|---|
| I6′ | `is_swing = is_whiff + is_contact`; `is_contact ⇔ pitch_call_h ∈ {Foul, InPlay}` | exacta (sin `Undefined`) |
| I9 | `altitude_category` constante dentro de cada `game_anon_id` | 100 % de los juegos con cubeta |
| I10 | `Outs ∈ {0,1,2}` | se reporta el conteo de violaciones |

**Compuertas redefinidas en v2.4 (ADR-010 a 013):**

| Compuerta | v2.3 | v2.4 |
|---|---|---|
| G0.1 | I1, I2, I6′ ≥ 99.9 % | I1, I2 ≥ 99.9 % · I6′ ≥ 99.5 % **y** tabla de discrepancias `is_*` × `pitch_call_h` (el árbol ya no depende de las banderas) |
| G0.2 | I3 ≥ 99 % o convención documentada | Matriz 3×3 producida **y** (permutación con signo con $R^2\ge0.99$ en los tres ejes, **o** ADR-010 declara los polinomios no canónicos). En ambos casos pasa, porque la trayectoria canónica es 9P |
| G0.3 | I7 ≥ 90 % | Criterio B ≥ 95 % de las medias entradas no finales **y** diagnóstico de las de 2 outs producido |
| G0.6 | exclusiones ≤ 3 % | `excluir_modelo` ≤ 3 % · `excluir_cadena` ≤ 0.5 % |

**Prompt de corrección F0 (v2.4, Sonnet, misma rama `fase00`):**

```text
Haz git pull de main y rebase de fase00 sobre main. ROADMAP.md está en v2.4: lee
§1.2 (ADR-010 a 013) y las compuertas redefinidas de §4-F0. En la rama fase00:
1. ADR-010: en qa.py, matriz 3×3 de regresiones (pendiente, intercepto, R²) de
   c2 de cada eje del polinomio sobre ax0/ay0/az0, y de c1 sobre vx0/vy0/vz0.
   Busca la permutación con signo de mejor R² mínimo. Si c1 encaja con un
   intercepto ≠ 0, estima el desplazamiento de tiempo t_s = (c1 − v0)/a0.
   Reporta la matriz y la decisión. Agrega en src/pitcheo/fisica.py la
   función trayectoria_9p(t) = r0 + v0 t + ½ a t² como trayectoria canónica.
2. ADR-011: columnas es_swing, es_whiff, es_contacto, es_foul, es_bip derivadas de
   pitch_call_h. Tabla de discrepancias (agregada) contra is_swing, is_whiff,
   is_contact, is_ball_in_play: cada combinación con su n.
3. ADR-012: criterios A y B de completitud por media entrada; columnas
   media_entrada_A y media_entrada_B. Diagnóstico de las medias entradas de 2
   outs: % última del juego; si OutsOnPlay cuenta el out de los ponches (tabla
   OutsOnPlay × evento_terminal=K); número de lanzamientos por media entrada vs.
   las de 3 outs; y eventos terminales de su último turno reconstruible.
4. ADR-013: banderas excluir_modelo y excluir_cadena con motivo.
5. Sintético: reproduce los ejes del polinomio con la convención que resulte del
   punto 1 si existe; si no, déjalo como está. Reproduce medias entradas de 2
   outs, filas con pitcher_anon_id nulo y fouls con KorBB=Strikeout. Una prueba
   por caso.
6. ADR-010 a 013 en docs/DECISIONES.md citando ROADMAP §1.2. Compuertas v2.4.
```
*(+ sufijo §0.3)*

**Prompt (Sonnet):**

```text
Lee CLAUDE.md, ROADMAP.md §4-F0 y reports/FASE_00_0.md (resultado real de la fase
anterior: úsalo para ajustar tipos y categorías reales en el código y en el
generador sintético).

1. `pitcheo f00`: lee data/raw/stuff_model_df.parquet (fuente canónica) y escribe
   data/interim/pitches.parquet particionado por year, con tipos normalizados
   (is_* a bool, categóricas a Enum de polars). data/raw/ es de solo lectura; el
   .pkl y el .rds ya no se usan.
2. Lee ROADMAP §1.1. Crea config/categorias.yaml con TODOS los valores reales de
   reports/FASE_00_0.md y sus mapas (familia, pitch_call_h, evento terminal).
   Implementa en src/pitcheo/limpieza.py los ADR-002 a ADR-007 exactamente como
   están escritos; escribe cada ADR en docs/DECISIONES.md citando ROADMAP §1.1.
   Columnas nuevas: familia, es_sweeper, pitcher_throws_r, batter_side_r,
   pitch_call_h, evento_terminal, excluir_modelo (bool con motivo en
   motivo_exclusion). Las columnas crudas se conservan. Si algún valor real no tiene
   regla, NO lo asignas: va a la tabla "sin regla" del reporte y la fase falla.
3. src/pitcheo/qa.py: identidades I1–I5, I6′, I7, I8, I9, I10 con su % de
   cumplimiento. Pruebas en tests/test_qa.py y tests/test_limpieza.py.
4. Actualiza src/pitcheo/sintetico.py para que reproduzca cada caso real: los 12
   AutoPitchType, manos Undefined y Switch, los tres FoulBall y Undefined, cubeta
   nula (en juegos completos y sueltos), Outs=3, y los 16 play_result con sus
   frecuencias aproximadas. Una prueba por caso.
5. Alcance (agregado): tabla year × altitude_category (juegos, lanzadores,
   lanzamientos); lanzadores por número de cubetas; tabla de frecuencias
   play_result × pitch_call_h × KorBB con el evento asignado; conteo de imputaciones
   y exclusiones por ADR (cuántas filas, %).
6. scripts/fases/f00.sh según el sufijo §0.3.
Compuertas (redefinidas en v2.4; ver tabla de arriba): G0.1 I1, I2 ≥ 99.9 % e
I6′ ≥ 99.5 % con tabla; G0.2 matriz 3×3 y decisión ADR-010; G0.3 criterio B ≥ 95 %
con diagnóstico; G0.4 I9 = 100 %; G0.5 cero valores "sin regla"; G0.6
excluir_modelo ≤ 3 % y excluir_cadena ≤ 0.5 %.
```
*(+ sufijo §0.3)*

**Compuertas redefinidas en v2.5 (§1.3):** G0.2 y G0.3 cambian; se agregan G0.7 y G0.8.

| Compuerta | v2.5 |
|---|---|
| G0.2 | ADR-010 enmendado: permutación (X→y, Y→z, Z→x) confirmada con la regresión conjunta de $c_2$ ($R^2\ge0.9999$) **y** $c_1$ ajustado con $t_s$ por lanzamiento ($R^2\ge0.999$ en los tres ejes) |
| G0.3 | Diagnóstico de las de 2 outs producido **y** clasificado: % con turno incompleto (robo o pickoff) vs. % con turno final perdido |
| **G0.7** | Verificación de ADR-014 con $t_p$ de la raíz de $y(t)=y_p$, con el $y_p$ y el signo elegidos: mediana de $\lvert$error$\rvert$ ≤ 0.05 ft en `PlateLocSide` y en `PlateLocHeight`, p99 ≤ 0.3 ft; y mediana de $\lvert$`ZoneTime`$-(t_p-t_s)\rvert$ ≤ 0.005 s |
| **G0.8** | Tasa de medias entradas con turno final perdido por cubeta (todos los años juntos): máximo − mínimo ≤ 3 puntos porcentuales. Si falla: **discrepancia, no se sigue a F1** |

**Prompt de corrección 2 de F0 (v2.5, Sonnet, misma rama `fase00`):**

```text
Haz merge de main en fase00 (no rebase). ROADMAP.md está en v2.5: lee §1.3 y las
compuertas v2.5 de §4-F0. En la rama fase00:
1. ADR-010 (enmienda): t_s por lanzamiento con t_s = (c1_X − vy0)/ay0; distribución
   (mediana, IQR, p1, p99). Regresión de c1 de cada eje del polinomio sobre
   (v0 + a0·t_s) del eje permutado: R² y pendiente. Reclasifica a "equivalentes"
   si se cumple G0.2.
2. ADR-014 en src/pitcheo/fisica.py: tiempo_al_plato(y_p) = raíz de
   y0 + vy0 t + ½ ay0 t² = y_p (la raíz positiva menor); elige y_p ∈ {17/12, 0}
   y el signo s ∈ {+1, −1} de PlateLocSide = s·x(t_p) por mínimo error mediano;
   reporta la tabla de las 4 combinaciones. Verifica ZoneTime ≈ t_p − t_s.
   Deja en config/default.yaml el y_p y el signo elegidos.
3. ADR-012/015: clasifica cada media entrada no final de 2 outs como
   "turno incompleto" o "turno final perdido"; tasa de "turno final perdido" por
   cubeta × año y por cubeta (todos los años), con IC binomial de Wilson.
   Déficits de eventos (K, OUT_BIP, SAC) y π̂_K de §1.3 con IC por bootstrap de
   medias entradas. NO implementes todavía los pesos ω (eso es F4).
4. Sintético: polinomio con permutación X→y, Y→z, Z→x y origen en la liberación;
   ZoneTime desde la liberación; PlateLocSide con el signo que elijas como
   verdadero en el generador; turnos finales perdidos con más probabilidad si
   terminan en K. Una prueba por caso: el código debe recuperar t_s, y_p, el
   signo y π_K sembrados.
5. ADR-010 (enmienda), ADR-014 y ADR-015 en docs/DECISIONES.md citando §1.3.
```
*(+ sufijo §0.3)*

**Compuertas redefinidas en v2.6 (§1.4):** G0.8 se sustituye por G0.8′ y se agrega G0.9 (reglas en §1.4). El resto queda como en v2.5.

**Prompt de corrección 3 de F0 (v2.6, Sonnet, misma rama `fase00`):**

```
Haz merge de main en fase00 (no rebase). ROADMAP.md está en v2.6: lee §1.4
(ADR-016, Props. 16–17, reglas de decisión) y las compuertas v2.6 de §4-F0.
Las reglas y umbrales ya están fijados: impleméntalos tal cual, sin ajustarlos.
1. Conjunto T: medias entradas no finales, Inning ≤ 9, consistentes (outs
   registrados ≤ 3), sin turno incompleto; reporta cuántas excluye cada filtro.
   O_h = Σ OutsOnPlay; P = {O_h = 2}; N_h = nº de turnos con evento_terminal ∈
   {1B,2B,3B,BB,HBP,ROE}; Z_h = 1[N_h = 0].
2. Prop. 16, por cubeta y global: f_b = media de Z en T_b; p0_b = fracción de
   T_b que está en P con Z = 1; r̂_b = p0_b / f_b; θ̂_b = r̂_b / P(P | b).
   IC95 por bootstrap de juegos (1000 réplicas, semilla de config, tabla ordenada
   de forma determinista antes de remuestrear).
3. Prop. 17: m̃_b = turnos por media entrada en T_b; n_b = turnos de la cubeta;
   κ̄ = K / turnos global (una sola cifra, no por cubeta);
   W(Γ) = Σ_{b ∈ {Extreme, No}} Γ·r̂_b / (m̃_b + Γ·r̂_b) con Γ = 1 y Γ = 2;
   SE_ref = sqrt(κ̄(1−κ̄)(1/n_Ext + 1/n_No)).
4. Compuertas G0.8′ y G0.9 con las reglas exactas de §1.4. Con --aplicar
   (como ADR-014) escribe en config/default.yaml qa.mecanismo_outs ∈
   {U, L, mezcla} y qa.perdida_ignorable (bool), para F4, F6 y F8.
5. Corroboraciones (informativas, no compuertas):
   (a) % de rodados (hit_type GroundBall; si la categoría no existe, Angle < 10°)
       entre OUT_BIP con Outs ∈ {0,1}: P vs. T∖P;
   (b) columna Outs (estado previo), P vs. T∖P: % con mínimo Outs > 0; % con un
       evento de out en un lanzamiento con Outs = 2; % con un hueco en los
       valores de Outs;
   (c) logit de 1[h ∈ P] sobre cubeta + year, sin y con factor(min(N_h, 5)),
       errores agrupados por juego: OR de cada cubeta vs No Altitude con IC95;
   (d) tabla de jugadas con OutsOnPlay ≥ 2 por evento, junto al número de
       dobles matanzas esperado a tasa MLB (1.63 por juego, solo referencia);
   (e) figura agregada docs/figuras/f00/P_por_juego_vs_poisson.png: histograma
       de |P| por juego contra Poisson con la misma media.
6. Limpieza del reporte:
   - renombra "turno final perdido" → "out faltante (sin turno incompleto)";
   - elimina π̂_K del reporte y del Bloque; la tabla de déficits queda como
     informativa;
   - la tasa de P por cubeta (antiguo G0.8) queda como tabla informativa;
   - I3 se marca "sustituida por G0.2 (ADR-010)";
   - I8: para cada tipo que falle, mediana de |HorzBreak| por mano; si es
     < 2 in, márcalo "no informativo".
7. Sintético: simulador base-out por media entrada (outs, corredores en
   1B/2B/3B, avance simple) con:
   - tráfico mayor en Extreme;
   - doble matanza en out de rodado con corredor en 1B y < 2 outs, calibrada a
     ≈ 1.6–2.0 por juego;
   - OutsOnPlay = 1 en el 93 % de las dobles matanzas y OutsOnPlay = 1 siempre
     en K;
   - corredor colocado en 2B en extra innings;
   - columna Outs previa = outs reales;
   - pérdida de turnos de out con tasa ℓ_b por cubeta y sesgo a K configurables.
   Pruebas:
   (i)   ℓ = 0 en todas las cubetas → θ̂ ≤ 0.05 y rango de la tasa de P entre
         cubetas > 3 pp (reproduce la falla real de v2.5);
   (ii)  ℓ = (0, 3, 6) % → r̂_b recupera ℓ_b ± 1 pp (usa juegos suficientes);
   (iii) los extra innings con corredor colocado no entran en T;
   (iv)  G0.8′ con tablas hechas a mano a ambos lados del umbral 3.92·SE_ref y de
         SE_ref (pasa / falla / perdida_ignorable).
8. ADR-016 en docs/DECISIONES.md citando §1.4. En docs/discrepancias/D01.md
   agrega: "Resuelta por ADR-016: se acepta la crítica; π̂_K se retira".
```

*(+ sufijo §0.3)*

**Salidas:** `data/interim/pitches.parquet` (local), `reports/FASE_00.md`.

---

### F1 — Pre-registro de hipótesis

**Modelo:** Opus · **Duración:** 1 h · **Sin corrida local.** Se hace merge a `main` antes de que cualquier fase con outcomes corra en local: el timestamp del commit es la evidencia del pre-registro.

**Hipótesis formales.** Etiquetas de evidencia: 🟢 confirmada tras BH · 🟡 medida, no sobrevive BH · ⚪ no detectada · 🔎 exploratoria. Control de falsos descubrimientos: **Benjamini–Hochberg con $q=0.10$ sobre todas las pruebas confirmatorias juntas.**

| ID | Afirmación | Estadístico | Regla 🟢 |
|---|---|---|---|
| H1 | La densidad escala el movimiento Magnus | $\beta$ en $\log\lVert\mathbf a_\perp\rVert_i=\alpha_{jk}+\beta\log\hat\rho_g+\varepsilon$ (efectos fijos lanzador×forma) | $p_{BH}<0.10$ y IC95 de $\beta$ ⊂ (0.7, 1.3); la física predice $\beta=1$ |
| H2 | El cambio gana Stuff+ **relativo** en altura | $\Delta^{rel}_{CH}-\Delta^{rel}_{SL\cup CU}$, familias de ADR-002 (CH incluye Splitter; SL incluye Sweeper) | unilateral $>0$, bootstrap por lanzador |
| H3 | El rodado vale más en altura | DiD: $[\bar w_{FB,alta}-\bar w_{FB,baja}]-[\bar w_{GB,alta}-\bar w_{GB,baja}]$ condicionado en EV×LA | $>0$ con $p_{BH}<0.10$ |
| H4 | El spin rate solo es insuficiente | $\Delta\text{LogLoss}$ (modelo con $\varepsilon,\omega_T$, movimiento) − (modelo con spin rate) | Diebold–Mariano por juego, $p_{BH}<0.10$ |
| H5 | Invariancia de la respuesta del bateador | En leave-high-bucket-out: pendiente $b$ de recalibración logística de N1–N4 en la cubeta alta; $\Delta$LogLoss por agregar el término de cubeta (LRT solo informativo) | **Equivalencia (TOST, enmienda v2.8):** IC90 de $b$ por bootstrap de juegos ⊂ [0.95, 1.05] **y** $\Delta$LogLoss ≤ 0.1 % de la log-loss base, en cada nodo. Fuera del BH |
| H6 | Stuff+ es más fiable que el valor observado | split-half de Stuff+ vs. de rv observado, mismo lanzador×tipo | Stuff+ mayor, IC bootstrap sin 0 |

H5 es la hipótesis que **justifica el operador contrafactual** (Prop. 7, F3). Si H5 falla, el contrafactual de F8 cambia de diseño: se escala al orquestador.

**Prompt (Opus):**

```text
Lee CLAUDE.md, ROADMAP.md (v2.7) §1.1–§1.5 y §4-F1, y reports/FASE_00.md.
Rama fase01 desde main.
1. docs/HIPOTESIS.md con H1–H6 tal cual están en §4-F1 (no cambies estadísticos
   ni reglas 🟢). Para cada una: variables exactas (diccionario y columnas de F0:
   familia, pitch_call_h, evento_terminal, es_*), unidad de análisis, filtros
   (excluir_modelo / excluir_cadena), agrupamiento de errores (juego o lanzador)
   y por qué, tamaño de efecto mínimo relevante con su justificación, qué
   resultado la refuta, y la lista exacta de pruebas que entran al único
   Benjamini–Hochberg (q = 0.10).
2. Sección "Datos faltantes (ADR-016)": mecanismo U, perdida_ignorable = false.
   Toda prueba que compare outcomes observados entre cubetas (H3 y la
   corroboración de F8) se reporta también con intervalo de Imbens–Manski con
   las cotas de la Prop. 17. Regla pre-registrada: 🟢 exige BH y además que el
   intervalo IM excluya el nulo; si pasa BH pero el IM no lo excluye, 🟡.
3. Sección "Lo visto antes del pre-registro": cifras por cubeta de
   reports/FASE_00.md (alcance, f_b, tasa de P, OR del logit) y la declaración
   de que ninguna es estadístico de H1–H6.
4. docs/DECISIONES.md YA EXISTE con ADR-002 a 016: no lo reescribas. Agrega al
   inicio la plantilla de ADR (contexto, decisión, alternativas, consecuencias)
   y el ADR-001: "ρ por juego desde la trayectoria porque el dataset no trae
   estadio ni clima".
5. No ejecutes ningún análisis ni leas datos. Esta fase no tiene corrida local.
6. Revisa la coherencia con ROADMAP y FASE_00.md. Si hay una contradicción,
   escribe docs/discrepancias/D01_F1.md y DETENTE sin hacer merge.
7. PR a main y merge. Escribe reports/FASE_01.md con el hash del commit de merge
   (evidencia del pre-registro) y el Bloque para el orquestador. Crea el tag
   fase01; si no puedes empujarlo, dame el comando exacto para Rodrigo.
```

---

### F2 — Densidad del aire por juego desde la trayectoria (núcleo)

**Modelo:** Opus (diseño) → Sonnet (implementación) → Opus (auditoría) · **Duración:** 5–7 h

**Objetivo.** Estimar $\hat\rho_g$ para cada juego usando solo la física del lanzamiento, validar contra la barométrica y descartar sesgo de sensor.

**Modelo físico.**

$$\ddot{\mathbf r}=\mathbf g-\kappa\,C_D\lVert\mathbf v\rVert\mathbf v+\kappa\,C_L\lVert\mathbf v\rVert^2\hat{\mathbf n},\qquad \hat{\mathbf n}=\frac{\boldsymbol\omega_T\times\mathbf v}{\lVert\boldsymbol\omega_T\times\mathbf v\rVert}\perp\mathbf v$$

**Proposición 1 (descomposición arrastre–Magnus).** Sea $\tilde{\mathbf a}=\mathbf a-\mathbf g$ con $\mathbf a=(a_{x0},a_{y0},a_{z0})$ y $\bar{\mathbf v}=\mathbf v_0+\mathbf a\,t_m$, $t_m=\tfrac12(t_s+t_p)$ (punto medio entre liberación y plato en el reloj de los 9P, ADR-014). Entonces

$$\rho C_D=-\frac{2m}{A}\,\frac{\tilde{\mathbf a}\cdot\hat{\bar{\mathbf v}}}{\lVert\bar{\mathbf v}\rVert^2},\qquad \rho C_L=\frac{2m}{A}\,\frac{\lVert\tilde{\mathbf a}-(\tilde{\mathbf a}\cdot\hat{\bar{\mathbf v}})\hat{\bar{\mathbf v}}\rVert}{\lVert\bar{\mathbf v}\rVert^2}$$

*Demostración.* Como $\hat{\mathbf n}\perp\mathbf v$, proyectar la ecuación de movimiento sobre $\hat{\mathbf v}$ elimina el término Magnus: $\tilde{\mathbf a}\cdot\hat{\mathbf v}=-\kappa C_D\lVert\mathbf v\rVert^2$. El residuo perpendicular es $\kappa C_L\lVert\mathbf v\rVert^2\hat{\mathbf n}$, de norma $\kappa C_L\lVert\mathbf v\rVert^2$. Multiplicar por $2m/A$ despeja $\rho C$. ∎

*Error.* El ajuste 9P supone $\mathbf a$ constante; la real escala con $\lVert\mathbf v\rVert^2$, que cae ~15–20 % en vuelo. Evaluar en $t_m$ es la regla del punto medio: error de **segundo orden**. Se cuantifica en la prueba sintética.

**Proposición 2 (identificación de $\rho_g$).** Sea $y^D_i=\log(\rho C_D)_i$. Si

$$y^D_i=\delta_{g(i)}+f_D(S_i,k_i,h_i,\text{year})+\eta_i,\qquad \mathbb E[\eta_i\mid\cdot]=0,$$

con $f_D$ común a todos los juegos (misma pelota, misma física) y soporte común de $(S,k)$ entre juegos (condición de rango), entonces $\delta_g-\delta_{g'}=\log(\rho_g/\rho_{g'})$ está identificado. Con la normalización $\bar\delta_{\text{No Altitude}}:=0$ (la cubeta baja es la referencia; contiene parques de 0 a ~600 m, $\rho/\rho_0\in[0.94,1.00]$), $\hat\rho_g/\rho_{ref}=e^{\hat\delta_g}$ y $\operatorname{Var}(\hat\delta_g)\approx\sigma_\eta^2/n_g$. Las cubetas no traen altitud numérica, así que no se normaliza a una barométrica absoluta.

*Demostración.* Modelo de efectos fijos con covariable flexible común: la diferencia de dos efectos fijos es estimable si la matriz de diseño de los dummies, una vez proyectada fuera del espacio de $f_D$, tiene rango completo, lo que se cumple bajo soporte común. El nivel absoluto no se identifica (cualquier constante pasa de $\delta$ a $f$), de ahí la normalización. ∎

*Precisión esperada.* Con ~250 lanzamientos por juego y $\sigma_\eta$ a medir, si $\sigma_\eta\approx0.15$ el error estándar de $\hat\delta_g$ es ≈ 0.01: **1 % de densidad por juego, contra una señal de 27 %.**

Lo mismo con $y^L_i=\log(\rho C_L)_i$ produce $\delta^L_g$. **Sobreidentificación:** bajo el modelo, $\delta^D_g=\delta^L_g$. Se prueba con regresión de Deming (ambos ruidosos): pendiente 1, intercepto 0.

**Proposición 3 (robustez a sesgos de calibración).** (a) Un error de escala espacial $\lambda_g$ por parque ($\tilde{\mathbf r}=\lambda\mathbf r$) da $\tilde{\mathbf v}=\lambda\mathbf v$, $\tilde{\mathbf a}=\lambda\mathbf a$, así que $\hat\delta_g$ absorbe $-\log\lambda_g$: un sesgo de 2 % produce 2 % de error, **un orden de magnitud bajo la señal** ($|\log0.762|=0.27$). (b) Un error de reloj $\tau$ da $\tilde{\mathbf v}=\mathbf v/\tau$, $\tilde{\mathbf a}=\mathbf a/\tau^2$: el cociente $\mathbf a/\lVert\mathbf v\rVert^2$ es invariante salvo el término $\mathbf g(\tau^{-2}-1)$, que carga en la vertical. Como $|\hat{\mathbf g}\cdot\hat{\mathbf v}|$ es pequeño (lanzamiento casi horizontal), el canal de arrastre casi no se afecta y el de sustentación sí.

*Consecuencia.* Un sesgo de sensor no puede fabricar el efecto altitud, y deja huella: discrepancia arrastre/sustentación concentrada en la componente vertical. **La prueba de sobreidentificación es el detector.** ∎

**Parques latentes (🔎 exploratorio).** Por juego: $\hat\delta_g$, residuo medio de `RelHeight` tras efecto fijo de lanzador (altura del montículo y calibración), sesgo medio de `PlateLocHeight`. Mezcla gaussiana con BIC sobre $\hat\delta_g$ dentro de cada cubeta. La componente de menor densidad dentro de *Extreme* define $\rho_{CDMX}$ (ADR-005). Con los juegos de cubeta nula se prueba si $\hat\delta_g$ predice su cubeta (🔎).

**Prompt 1 (Opus, diseño):**

```text
Lee ROADMAP.md §4-F2 completo. Antes de escribir código, escribe en
docs/MODELO_MATEMATICO.md la sección "F2" con las Proposiciones 1–3 en tus palabras,
el sistema de coordenadas exacto de Trackman según el diccionario, las conversiones
a SI y el diseño de:
 (a) una prueba sintética: simular con solve_ivp (DOP853) 5 000 lanzamientos con ρ
     conocida en 3 niveles (1.00, 0.82, 0.76·ρ0), C_D y C_L realistas, ajustar un
     modelo 9P de aceleración constante por mínimos cuadrados sobre posiciones con
     ruido, y recuperar ρ con el estimador de la Prop. 2;
 (b) el estimador de efectos fijos con f_D como B-spline de S por forma×mano×año;
 (c) la prueba de Deming δ^D vs δ^L.
Si algo de la Proposición 1–3 es incorrecto o mejorable, escríbelo en
docs/discrepancias/D02a.md y DETENTE. No implementes.
```

**Prompt 2 (Sonnet, implementación):**

```text
Lee docs/MODELO_MATEMATICO.md sección F2 e implementa en src/pitcheo/fisica.py:
descomposicion_arrastre_magnus(), estimador_densidad_juego() y la prueba sintética en
tests/test_fisica_sintetica.py, extendiendo src/pitcheo/sintetico.py con física
exacta (ρ conocida por cubeta). La sintética corre AQUÍ: si el error de recuperación
de ρ supera 1 %, DETENTE y reporta (G2.1). Lo siguiente va en `pitcheo f02` y
scripts/fases/f02.sh para la corrida local:
 - data/interim/densidad_juego.parquet con g, δ^D, δ^L, SE, n_g, cubeta.
 - Tabla: media de δ^D por cubeta vs log ρ barométrica (ROADMAP §2); pendiente e IC.
 - Deming δ^L sobre δ^D; descomposición de la discrepancia por componente vertical.
 - Dispersión de δ dentro de cada cubeta (clima + varios parques).
 - Parques latentes (GMM + BIC) marcado como 🔎.
Figuras a docs/figuras/f2/. reports/FASE_02.md con el Bloque para el orquestador.
```

**Prompt 3 (Opus, revisión tras la corrida local):** el prompt de revisión §0.4, más: *"Verifica unidades, signos de los ejes, normalización y que ningún outcome se usó."*

**Compuertas:**
- **G2.1** Error sintético de recuperación de ρ < 1 %.
- **G2.2** (a) Orden estricto $\bar\delta_{\text{No}}>\bar\delta_{\text{Medium}}>\bar\delta_{\text{Extreme}}$. (b) $\bar\delta_{\text{Extreme}}\in[-0.30,-0.15]$ (aire entre 74 % y 86 % del de la cubeta baja, compatible con parques de ~1 600 a ~2 300 m). (c) La componente más densa de altura de *Extreme* en la mezcla tiene media en $[-0.32,-0.20]$, compatible con 2 200 m respecto a una referencia de 0–600 m.
- **G2.3** Deming $\delta^L$ sobre $\delta^D$: pendiente ∈ [0.85, 1.15].
- **G2.4** $\sigma_\eta$ medida y error estándar mediano de $\hat\delta_g$ < 0.03.

**Si G2.2 falla con G2.3 aprobada:** las cubetas no corresponden a la altitud supuesta. **Si G2.3 falla:** sesgo de sensor; ver Prop. 3. Ambos casos van al orquestador.

---

### F3 — Invariantes, eficiencia de giro y operador de traslación $T$

**Modelo:** Opus (diseño) → Sonnet · **Duración:** 4–5 h

**Objetivo.** Separar lo que es del lanzador (invariante a ρ) de lo que es del aire, y construir $T_{\rho\to\rho'}$.

**Eficiencia de giro empírica.** $C_{L,i}=(\rho C_L)_i/\hat\rho_{g(i)}$. La envolvente $C_L^{\max}(S)$ es el **cuantil 0.95** de $C_L$ dado $S$, ajustado con LightGBM `objective=quantile`, `alpha=0.95` y restricción monótona creciente en $S$. Definimos

$$\varepsilon_i=\frac{C_{L,i}}{C_L^{\max}(S_i)}\in(0,\approx1],\qquad \omega_{T,i}=\varepsilon_i\,\omega_i .$$

Es una definición sin modelo paramétrico de $C_L(S)$: "qué fracción de la sustentación máxima posible a ese factor de giro logra este lanzamiento". Responde directamente a H4.

**Vector invariante** $\psi_i$: velocidad de salida, $\omega$, $\varepsilon$, $\omega_T$, dirección de $\hat{\mathbf n}$ (seno y coseno), $C_D$, $C_L$, `RelHeight`, `RelSide`, `Extension`, `VertRelAngle`, `HorzRelAngle`.
**Vector realizado** $z_i$ (depende de ρ): `InducedVertBreak`, `HorzBreak`, `ZoneSpeed`, `SpeedDrop`, `ZoneTime`, VAA.

**Operador $T_{\rho\to\rho'}$.** Integrar la ecuación de F2 con DOP853 desde la liberación hasta el plano del plato $y=y_p$ elegido en ADR-014 con condiciones iniciales observadas, $C_D,C_L,\hat{\mathbf n}$ fijos y $\kappa(\rho')$. Devuelve $z'$ y el **desplazamiento de ubicación** en el plato.

**Proposición 4 (escalamiento lineal del movimiento).** La desviación Magnus a lo largo de una distancia $D$ es

$$d_M\approx\tfrac12\,\kappa C_L\lVert\bar{\mathbf v}\rVert^2 t_f^2\approx\tfrac12\kappa C_L D^2=\frac{\rho A C_L D^2}{4m}\quad\Rightarrow\quad\frac{d_M(\rho')}{d_M(\rho)}\approx\frac{\rho'}{\rho}.$$

*Demostración.* Con $t_f\approx D/\lVert\bar{\mathbf v}\rVert$, la velocidad se cancela; $C_L$ depende de $S=r\omega/v$, que no depende de ρ a primer orden. Correcciones de segundo orden: con menos arrastre, $\bar v$ sube, $S$ baja y $C_L$ baja ligeramente, así que el movimiento cae aún un poco más. ∎

*Validación de la proposición:* con $\rho'/\rho=0.823$ (Denver) predice 18" → 14.8", dentro del 14–15" de Nathan. Análogamente, la pérdida relativa de velocidad $\approx\kappa C_D D\propto\rho$, así que `SpeedDrop` también escala con ρ.

**Proposición 5 (mediación por la trayectoria; justifica el contrafactual).** Si $Y\perp\rho\mid(z,c,h)$ (H5), entonces

$$\mathbb E[Y\mid x\text{ lanzado en }\rho']=m\big(T_{\rho\to\rho'}(x),c,h\big),\qquad m(z,c,h)=\mathbb E[Y\mid z,c,h].$$

*Demostración.* $T$ es determinista, así que $z'=T(x)$ es la trayectoria que el bateador vería en $\rho'$. Por la independencia condicional, la respuesta solo depende de $z'$. ∎ Vale para swing, whiff y strike cantado. **No** vale para el valor del batazo (el carry depende de ρ directamente), por eso ese nodo lleva el entorno como feature (F6).

**Prompt (Opus → Sonnet):**

```text
[Opus] Lee ROADMAP §4-F3 y docs/MODELO_MATEMATICO.md (F2). Agrega la sección F3:
definición de ε por envolvente cuantílica, ψ, z, el operador T (ecuaciones, evento de
término, tolerancias rtol=1e-8) y las Proposiciones 4–5. Señala en D03a.md cualquier
supuesto débil. No implementes.

[Sonnet] Implementa src/pitcheo/operador.py: envolvente C_L^max(S) (LightGBM
quantile 0.95, monótona en S), ε, ω_T, ψ, z, y T(x, ρ, ρ'). Pruebas:
 - Autoconsistencia: T_{ρ̂g→ρ̂g}(x) reproduce z observado (RMSE por componente).
 - Nathan: un lanzamiento con 18" de break a ρ0 → ρ=0.823ρ0 da 14–15".
 - Validación cruzada intra-lanzador: para lanzador×forma con ≥ 30 lanzamientos en
   cubeta baja y ≥ 30 en alta, compara el IVB/HB medio observado en alta contra
   T(baja→alta) aplicado a sus lanzamientos de cubeta baja. Regresión observado ~
   predicho: pendiente e IC por bootstrap por lanzador.
Guarda data/interim/invariantes.parquet. reports/FASE_03.md con el Bloque.
```

**Compuertas:**
- **G3.1** Autoconsistencia: RMSE de IVB y HB < 1.0".
- **G3.2** Prueba de Nathan dentro de [14, 15]".
- **G3.3** Pendiente observado~predicho intra-lanzador ∈ [0.85, 1.15].

---

### F4 — Variable objetivo: pesos lineales, cadena de conteos y valor del batazo

**Modelo:** Opus (diseño) → Sonnet · **Duración:** 4–5 h · **En paralelo con F5.**

**4.1 Pesos lineales por media entrada.** El modelo principal lo fija G0.9 (§1.4). Si **U dominante**: modelo **C** (todas las medias entradas de $T$ con regresor $u_h=3-O_h$, outs no contabilizados: dobles matanzas y outs de corredor, con restricción $w_u\le0$); el criterio **A** queda como sensibilidad. Si **mezcla o L**: A principal y C sensibilidad. Con $N_{e,h}$ el número de eventos terminales $e\in\{1B,2B,3B,HR,BB,HBP,K,\text{OUT\_BIP},\text{ROE},\text{SAC}\}$ (ADR-007):

$$R_h=\sum_e w_e N_{e,h}+u_h .$$

Se estima por **mínimos cuadrados con restricciones de orden**, que es un problema de **programación cuadrática**:

$$\min_{\mathbf w}\ \lVert\mathbf R-N\mathbf w\rVert^2\quad\text{s.a.}\quad w_{HR}\ge w_{3B}\ge w_{2B}\ge w_{1B}\ge w_{BB}\ge0\ge\max(w_{K},\,w_{out}).$$

Es convexo (objetivo cuadrático, restricciones lineales), así que tiene óptimo global único si $N$ tiene rango completo. Pesos por cubeta: $w_e^{(b)}=w_e+\gamma^{(b)}_e$ con penalización ridge sobre $\gamma$ (el entorno de carreras de la altura cambia el valor de cada evento). IC por bootstrap de juegos.

*Nota.* Carreras por eventos no-PA (wild pitch, robos, errores) quedan en $u_h$: sesgan el intercepto, no las pendientes, si son independientes de la mezcla de eventos.

**4.2 Cadena de Markov de conteos.** No necesita orden: la transición de cada lanzamiento la determinan su conteo previo y su `PitchCall`. Estados transitorios: los 12 conteos. Absorbentes: K, BB/HBP, BIP. Si G0.9 = U dominante, las transiciones se cuentan sin pesos (no falta ningún lanzamiento). Si no, con los pesos $\omega$ de la Prop. 15 por cubeta, con $M_b=\hat r_b|T_b|$ y $\pi\in\{0,1\}$; no se usa $\hat\pi_K$ (ADR-016). En la regresión de 4.1, además del criterio A, se ajusta un modelo **C** con todas las medias entradas no finales y consistentes más un regresor "outs faltantes" $=3-\text{outs}_h$.

**Proposición 6 (existencia y unicidad del valor del conteo).** Sea $Q\in\mathbb R^{12\times12}$ la matriz transitoria (con autolazos en conteos de 2 strikes por foul) y $R$ la de absorción. Si desde todo conteo la absorción ocurre con probabilidad positiva en a lo más $m$ pasos, entonces $\rho(Q)<1$, $N=(I-Q)^{-1}=\sum_{k\ge0}Q^k$ existe, y

$$\mathbf V=N\,R\,\mathbf w_{term}$$

es el valor esperado del desenlace dado el conteo.

*Demostración.* Si cada estado se absorbe en ≤ $m$ pasos con probabilidad ≥ $p>0$, entonces $\lVert Q^m\rVert_\infty\le1-p<1$, así que $\rho(Q)<1$ y la serie de Neumann converge. $\mathbf V=R\mathbf w+Q\mathbf V$ es la ecuación de un paso; su solución única es $(I-Q)^{-1}R\mathbf w$. ∎ La hipótesis falla solo si P(foul ∣ 2 strikes) = 1, lo que no ocurre.

**Valor de carrera del lanzamiento** (perspectiva del bateador; Stuff+ usa $-rv$):

$$rv_i=\begin{cases}V(c')-V(c)&\text{si el lanzamiento no termina el turno}\\ w_{term}-V(c)&\text{si lo termina}\end{cases}$$

**4.3 Valor esperado del batazo (Rao–Blackwell).** Multiclase LightGBM sobre $\{\text{out},1B,2B,3B,HR\}$ con `ExitSpeed`, `Angle`, `Direction` y cubeta:

$$\hat w(z)=\sum_e \hat P(e\mid z)\,w_e^{(b)} .$$

**Proposición 7 (reducción de varianza sin sesgo).** Si el valor del batazo $Y$ es independiente de los rasgos del lanzamiento $X$ dado el contacto $Z$ (suficiencia del contacto), entonces $\mathbb E[\hat w(Z)\mid X]=\mathbb E[Y\mid X]$ y $\operatorname{Var}(\hat w)=\operatorname{Var}(Y)-\mathbb E[\operatorname{Var}(Y\mid Z)]\le\operatorname{Var}(Y)$.

*Demostración.* Torre de esperanzas y ley de la varianza total. ∎ Batazos sin `ExitSpeed`: imputar la media de su `hit_type`; reportar qué fracción son.

**4.4 Carry (insumo de H3).** En elevados (LA ∈ [20°, 40°]): $\log\text{Distance}=f(\text{EV},\text{LA})+\theta_b+\epsilon$. El multiplicador de carry es $e^{\theta_{alta}-\theta_{baja}}$. Es un **segundo canal físico independiente** de F2 para la misma densidad.

**Prompt (Opus → Sonnet):**

```text
[Opus] Lee ROADMAP §4-F4. Agrega a docs/MODELO_MATEMATICO.md la sección F4: mapeo
exacto de PitchCall/KorBB/play_result/is_hit_by_pitch a eventos terminales, el QP de
4.1, la Proposición 6 y la 7. Decide y documenta (ADR-008) qué hacer con BallIntentional,
bunts y medias entradas incompletas. Señala en D04a.md cualquier problema.

[Sonnet] Implementa src/pitcheo/objetivo.py:
 1. pesos_lineales(): QP con scipy.optimize.minimize (method="trust-constr") o lsq
    con restricciones; versión global y por cubeta con ridge; bootstrap de 1000
    remuestreos por juego.
 2. cadena_conteos(): Q, R, N, V; verifica ρ(Q)<1 numéricamente.
 3. valor_batazo(): multiclase LightGBM, calibración, ŵ.
 4. rv por lanzamiento con ŵ en lugar del valor observado del batazo.
 5. carry(): modelo de Distance con efecto de cubeta.
Guarda data/interim/objetivo.parquet. reports/FASE_04.md con el Bloque.
```

**Compuertas:**
- **G4.1** Pesos lineales cumplen el orden sin restricciones activas en más de un par (si muchas están activas, el modelo está mal especificado).
- **G4.2** $R^2$ fuera de muestra (medias entradas de juegos retenidos) ≥ 0.5.
- **G4.3** $V(B+1,S)\ge V(B,S)$ y $V(B,S+1)\le V(B,S)$ en todos los conteos.
- **G4.4** Multiclase del batazo calibrado: ECE < 0.02.
- **G4.5** Multiplicador de carry de la cubeta alta > 1 con IC sin 1.
- **G4.6** Pesos lineales A vs. C dentro de sus IC; si difieren, se reporta cuál es principal según G0.9. Si G0.9 ≠ U: $V(c)$ reportado con $\pi\in\{0,1\}$ por cubeta.

---

### F5 — Arsenal, agrupamiento por forma y auditoría de fugas

**Modelo:** Sonnet → Opus (auditoría) · **Duración:** 3–4 h · **En paralelo con F4.**

**5.1 Espejo de zurdos.** Para `PitcherThrows=Left`: $x\to-x$ en `HorzBreak`, `RelSide`, `x0`, `vx0`, `ax0`, `HorzRelAngle`, `HorzApprAngle`, $c_\cdot^{(x)}$; `SpinAxis` → $360°-$`SpinAxis`. Duplica efectivamente la muestra para formas.

**5.1b Desfase lateral (§1.5).** Antes del espejo: $\hat\delta_x$ con IC95 por bootstrap de lanzadores. Si el IC excluye 0 y $|\hat\delta_x|\ge0.5$ in, se refleja sobre $\delta_x$; si no, sobre 0. Reporta el resultado del Cutter.

**5.2 Formas.** Mezcla gaussiana sobre $\psi$ estandarizado (velocidad, IVB, HB, seno y coseno del eje, $\varepsilon$, altura de liberación, extensión) por mano; número de componentes por BIC. Concordancia con `AutoPitchType` por índice de Rand ajustado. Se usa la **probabilidad posterior** de pertenencia, no la etiqueta dura.

**5.3 Rasgos relacionales.** Recta primaria por lanzador×año: la familia de mayor uso entre {FF, SI} (ADR-002); si el lanzador no tiene ninguna con ≥ 10 % de uso, FC. Diferencias $\Delta v$, $\Delta$IVB, $\Delta$HB, $\lVert\Delta(x_0,z_0)\rVert$, uso. Con pocos lanzamientos, la media de la recta se encoge hacia la media de su forma (Bayes empírico, Prop. 10).

**5.4 Túnel estático exacto.** Con la trayectoria canónica 9P (ADR-010), $y(t)=y_0+v_{y0}t+\tfrac12a_{y0}t^2$, es decir $c_0=y_0$, $c_1=v_{y0}$, $c_2=\tfrac12a_{y0}$. El instante de decisión resuelve $y(t^\ast)=y_d$:

$$t^\ast=\frac{-c_1^{(y)}-\sqrt{(c_1^{(y)})^2-4c_2^{(y)}(c_0^{(y)}-y_d)}}{2c_2^{(y)}}$$

(raíz positiva más pequeña). Con la trayectoria media de la recta del lanzador, $d_{tun}=\lVert\Delta\mathbf r(t^\ast)\rVert$, $d_{plato}=\lVert\Delta\mathbf r(t_{plato})\rVert$, y la razón $d_{plato}/d_{tun}$: mucho movimiento tarde con poca separación temprana. Sensibilidad $y_d\in\{20,23,26\}$ ft.

**5.5 Auditoría de fugas de ubicación.** Una feature fuga ubicación si predice `PlateLocHeight` o `PlateLocSide` más allá de lo que explica la forma del lanzamiento.
- `EffectiveVelo` → sustituir por velocidad percibida sin ubicación: $v_{perc}=$`RelSpeed`$\cdot\frac{60.5}{60.5-\text{Extension}}$.
- `VertApprAngle` → $\text{nVAA}=\text{VAA}-\hat{\mathbb E}[\text{VAA}\mid\text{PlateLocHeight}]$ (por construcción, ortogonal a la altura).
- `HorzApprAngle` → análogo con `PlateLocSide`.

**Prompt (Sonnet → Opus):**

```text
[Sonnet] Lee ROADMAP §4-F5. Implementa src/pitcheo/arsenal.py: espejo de zurdos,
GMM por mano con BIC (semilla en config), ARI vs AutoPitchType, recta primaria,
diferencias relacionales con encogimiento, túnel exacto con los polinomios para
y_d ∈ {20,23,26}, v_perc, nVAA y nHAA. Auditoría de fugas: con GroupKFold por
pitcher_anon_id, entrena LightGBM para predecir PlateLocHeight y PlateLocSide con
(a) solo forma+mano+velocidad y (b) cada feature candidata añadida; reporta el ΔR².
Guarda data/interim/features.parquet. reports/FASE_05.md con el Bloque.

[Opus] Audita: ¿alguna feature de Stuff+ puro usa información de ubicación o de
outcome, directa o indirectamente? ¿Los rasgos relacionales usan solo física del
mismo lanzador? Veredicto de compuertas.
```

**Compuertas:**
- **G5.1** $\Delta R^2$(ubicación ∣ cada feature final de Stuff+) ≤ 0.02.
- **G5.2** ARI(GMM, AutoPitchType) reportado. Si < 0.5, ADR que explique cuál se usa.
- **G5.3** Ninguna feature usa `*_anon_id` como valor ni columnas `target_only`.

---

### F6 — Modelos: Stuff+, Pitching+ y Location+

**Modelo:** Opus (diseño) → Sonnet · **Duración:** 6–8 h

**6.1 Árbol de desenlaces.** Nodos LightGBM:

| Nodo | Probabilidad | Condición |
|---|---|---|
| N1 | $P(\text{swing})$ | todos |
| N2 | $P(\text{whiff}\mid\text{swing})$ | swing |
| N3 | $P(\text{foul}\mid\text{contacto})$ | contacto |
| N4 | $P(\text{strike cantado}\mid\text{no swing})$ | no swing |
| N5 | $\mathbb E[\hat w\mid\text{BIP}]$ | en juego (regresión) |

Los nodos se definen desde `pitch_call_h` y `evento_terminal` (ADR-011), no desde las banderas `is_*`; así forman una partición exacta.

Auxiliares para el reporte: $P(\text{chase})$ con `swung_outside_strike_zone`, $P(\text{GB}\mid\text{BIP})$, $P(\text{contacto duro}\mid\text{BIP})$.

Con $\Delta_s(c)$ el cambio de valor por strike, $\Delta_b(c)$ por bola y $\Delta_f(c)=\Delta_s(c)\,\mathbb 1[S<2]$ por foul, la **ley de la esperanza total** sobre el árbol da exactamente

$$\text{xRV}(x,c)=p_1\Big[p_2\,\Delta_s(c)+(1-p_2)\big(p_3\,\Delta_f(c)+(1-p_3)(\mu_5-V(c))\big)\Big]+(1-p_1)\Big[p_4\,\Delta_s(c)+(1-p_4)\,\Delta_b(c)\Big]$$

donde $\Delta_s(c)=w_K-V(c)$ si $S=2$ y $\Delta_b(c)=w_{BB}-V(c)$ si $B=3$. **Los pesos de los targets no se eligen: salen de la cadena.** Esto responde a "Stuff+ final es una combinación ponderada".

**6.2 Conjuntos de features.**
- **Stuff+:** $\psi$, $z$ (con $v_{perc}$, nVAA), posteriores de forma, relacionales, túnel, mano de lanzador y bateador, conteo (solo para entrenar), entorno ($\hat\rho_g$ y cubeta, **solo en N5**, por Prop. 5).
- **Pitching+:** lo anterior más `PlateLocSide`, `PlateLocHeight`.

**Proposición 8 (Stuff+ neutral al conteo).** Con $\pi(c)$ la distribución de conteos de la liga, fija,

$$\text{xRV}^{S}(x)=\sum_c\pi(c)\,\text{xRV}(x,c).$$

Entonces el Stuff+ medio de un lanzador no depende de en qué conteos usa cada lanzamiento. *Demostración:* $\pi$ no depende del lanzador ni de $x$. ∎ Elimina el sesgo de "su slider sale en 0-2".

**Proposición 9 (Location+ centrado, vía integral).** Sea $m_P(x,\ell,c)$ el modelo Pitching+ y $p(\ell\mid k,c,h)$ una mezcla gaussiana de ubicaciones por forma, conteo y mano. Definimos

$$\bar m(x,c)=\int m_P(x,\ell,c)\,p(\ell\mid k(x),c,h)\,d\ell\approx\frac1K\sum_{r=1}^K m_P(x,\ell_r,c),\quad \ell_r\sim p,$$

y $L_i=m_P(x_i,\ell_i,c_i)-\bar m(x_i,c_i)$. Entonces $\mathbb E[L\mid x,c]=0$.

*Demostración.* Torre de esperanzas si $p$ es la condicional verdadera. ∎ Location+ mide valor sobre la ubicación típica de *ese* tipo de lanzamiento, y Pitching+ = Stuff+ + Location+ de forma aditiva. **Control de consistencia:** $\bar m$ por integral vs. el modelo Stuff+ directo: correlación > 0.9.

**6.3 Restricciones monótonas** (ablación): $v_{perc}$ y `Extension` decrecientes en xRV. Se conservan solo si la log-loss fuera de muestra empeora < 0.1 %.

**6.4 Validación cruzada anidada.** Externa: año (entrenar en $Y_1,Y_2$ → probar en $Y_3$; y rotación). Filas con `excluir_modelo` fuera (ADR-013). Interna: `GroupKFold(5)` por `pitcher_anon_id`. Calibración isotónica sobre predicciones fuera de fold.

**6.5 Proposición 10 (escala Stuff+).** Sea $s=-\text{xRV}^S$. Con $\mu,\sigma$ calculadas **una sola vez** sobre la población de referencia (medias lanzador×forma con $n\ge50$, evaluadas en el entorno neutral $\bar\rho$ de la liga, por año):

$$\text{Stuff+}=100+10\,\frac{s-\mu}{\sigma}.$$

Dos versiones, ambas reportadas:
- **Absoluta:** $\mu,\sigma$ comunes a todos los entornos. Permite ver que *todo* empeora en altura.
- **Relativa:** $\mu,\sigma$ recalculadas dentro de cada entorno. Permite ver *qué formas* pierden más que el promedio (H2).

*Por qué importa:* si se renormaliza dentro de CDMX, el lanzamiento promedio vuelve a ser 100 y el efecto altitud desaparece de la media. Es el error conceptual más fácil de cometer en este reto.

*Verificación:* si las medias son aproximadamente normales, 120 ↔ $\Phi(2)=97.7$ %, consistente con el "percentil ~97" del reto. Si el percentil empírico de 120 sale de [96, 99], reportar también la versión de rango normalizado $\Phi^{-1}(\text{rango})$.

**Prompt (Opus → Sonnet):**

```text
[Opus] Lee ROADMAP §4-F6. Escribe en docs/MODELO_MATEMATICO.md la sección F6: la
fórmula del árbol con los Δ exactos, Props. 8–10, el esquema de CV anidada y la
lista final de features de cada modelo con su justificación. ADR-009 sobre si
AutoPitchType entra como feature o solo las posteriores del GMM (decidir por
ablación en F7). Señala en D06a.md cualquier problema. No implementes.

[Sonnet] Implementa src/pitcheo/modelos.py: N1–N5 y auxiliares, CV anidada,
calibración isotónica, xRV por la fórmula del árbol, xRV^S neutral al conteo, Pitching+,
Location+ por Monte Carlo (K=64, semilla fija), escala absoluta y relativa,
ablación monótona. Baselines B0 (xRV medio por conteo), B1 (forma×conteo),
B2 (logística/lineal con las 8 features físicas del reto). Guarda predicciones
fuera de fold en data/interim/predicciones.parquet y modelos en artefactos/
(git-ignorado). reports/FASE_06.md con el Bloque.
```

**Compuertas:**
- **G6.1** Cada nodo supera a B1 en log-loss fuera de muestra.
- **G6.2** ECE < 0.01 en N1–N4 tras calibración.
- **G6.3** Correlación Stuff+ directo vs. integral > 0.9.
- **G6.4** Percentil empírico de 120 reportado.
- **G6.5** **Solo si G0.9 ≠ U dominante.** Correlación de Spearman del Stuff+ lanzador×familia entre las cotas $\pi=0$ y $\pi=1$ (ADR-015) ≥ 0.98. Si no, la pérdida de turnos finales afecta los rankings y se escala.

---

### F7 — Validación fuera de muestra

**Modelo:** Opus · **Duración:** 4–5 h

| Esquema | Qué prueba |
|---|---|
| Pitcher holdout (GroupKFold) | generaliza a lanzadores no vistos |
| Season holdout | estabilidad entre temporadas |
| Leave-one-bucket-out | generaliza entre entornos |
| **Leave-high-bucket-out** | prueba H5: entrenar sin cubeta alta y predecir N1–N4 en ella con los rasgos realizados |

**Pruebas:**
- **Diebold–Mariano** con diferencias de pérdida **agregadas por juego** (los lanzamientos de un juego no son independientes; los juegos sí, aproximadamente).
- **Murphy:** Brier = fiabilidad − resolución + incertidumbre, por nodo.
- **ECE** y curvas de calibración; AUC-PR para whiff.
- **Validez predictiva** (estilo Healey): Stuff+ del año $t$ vs. rv/100 del lanzador en $t+1$, comparado con rv/100 en $t$. Diferencia de correlaciones dependientes por bootstrap de lanzadores.
- **H5:** LRT del término de cubeta en N1–N4; pendiente e intercepto de calibración en leave-high-out.
- **Pruebas de fuga:** (a) targets permutados → AUC ≈ 0.5; (b) features permutadas una a una → caída de importancia coherente.

**Proposición 11 (fiabilidad y punto de estabilización).** Con correlación split-half $r$ entre mitades aleatorias de los lanzamientos de cada lanzador×forma, la fiabilidad con $n$ lanzamientos es $r_n=\frac{nr}{1+(n-1)r}$ (Spearman–Brown). El punto de estabilización $n^\ast$ con $r_{n^\ast}=0.5$ es $n^\ast=\sigma^2_{intra}/\tau^2_{entre}$. *Demostración:* modelo de efectos aleatorios de un factor, $\text{fiabilidad}=\tau^2/(\tau^2+\sigma^2/n)$. ∎ Insumo de H6 y del umbral $n\ge50$ de la escala.

**Prompt (Opus):**

```text
Lee ROADMAP §4-F7 y docs/HIPOTESIS.md. Implementa src/pitcheo/validacion.py con
los cuatro esquemas, baselines B0–B2, Diebold–Mariano por juego, descomposición de
Murphy, ECE, AUC-PR, validez predictiva t→t+1, split-half con Spearman–Brown y n*,
pruebas de fuga y la prueba de H5. Ablación de ADR-009 (AutoPitchType sí/no) y de
restricciones monótonas. Todas las IC por bootstrap por lanzador o juego, según
corresponda, 1000 réplicas. Tabla maestra en reports/FASE_07.md con el Bloque.
No adelantes veredictos de H1–H4: eso es F8.
```

**Compuertas:**
- **G7.1** Stuff+ y Pitching+ superan a B0 con DM $p<0.05$ en pitcher holdout **y** en season holdout.
- **G7.2** Validez predictiva: Stuff+$_t$ correlaciona con rv$_{t+1}$ más que rv$_t$.
- **G7.3** H5 por equivalencia (v2.8): IC90 de la pendiente ⊂ [0.95, 1.05] y $\Delta$LogLoss del término de cubeta ≤ 0.1 % en N1–N4. **Si falla:** el contrafactual de F8 cambia de diseño. Escalar al orquestador.
- **G7.4** Pruebas de fuga limpias.

---

### F8 — Efecto altitud: ΔStuff+ por forma y veredictos H1–H6

**Modelo:** Opus · **Duración:** 4–5 h

**Contrafactual por lanzamiento.** Con $\rho_{ref}$ = media de $\hat\rho_g$ en la cubeta *No Altitude* y $\rho_{CDMX}$ = media de la componente de menor densidad dentro de *Extreme* (ADR-005):

$$x_i^{ref}=T_{\hat\rho_{g(i)}\to\rho_{ref}}(x_i),\qquad x_i^{CDMX}=T_{\hat\rho_{g(i)}\to\rho_{CDMX}}(x_i),\qquad \Delta_i=\text{Stuff+}(x_i^{CDMX},e_{CDMX})-\text{Stuff+}(x_i^{ref},e_{ref}).$$

Si `qa.perdida_ignorable = false` (G0.8′), todo contraste de outcomes observados entre cubetas (incluida la corroboración intra-lanzador y H3) se reporta además con intervalo de Imbens–Manski (2004), con las cotas de la Prop. 17.

**Proposición 12 (descomposición de Shapley en dos factores).** Sea $f(x,e)$ el Stuff+ con movimiento $x$ y entorno de batazo $e$. Las contribuciones

$$\phi_{mov}=\tfrac12\big[f(x',e)-f(x,e)+f(x',e')-f(x,e')\big],\qquad \phi_{env}=\tfrac12\big[f(x,e')-f(x,e)+f(x',e')-f(x',e)\big]$$

suman exactamente $f(x',e')-f(x,e)$. *Demostración:* sumar y cancelar términos. ∎ Separa **"pierde por moverse menos"** de **"pierde porque le pegan y la pelota vuela"**: dos recomendaciones operativas distintas.

**Curva de elasticidad.** Como LightGBM es constante a trozos, $\partial f/\partial\rho=0$ casi en todas partes: la derivada puntual no sirve. Se evalúa $\overline{\text{Stuff+}}_k(\rho)$ en una rejilla $\rho/\rho_0\in[0.72,1.00]$ con paso 0.01, promediando sobre los lanzamientos de cada forma $k$ (el promedio sí es suave), y se reporta la pendiente local.

**Corroboración empírica** (independiente del modelo): modelo mixto intra-lanzador de outcomes observados $y_i=\alpha_j+\beta_k\cdot\mathbb 1[\text{alta}]+\cdots$. La pendiente de $\hat\beta_k$ sobre $\bar\Delta_k$ debe ser positiva y cercana a 1.

**Riesgo de jonrón.** $P(\text{HR}\mid\text{BIP})$ por forma y cubeta desde N5 y el multiplicador de carry de F4.4.

**Prompt (Opus):**

```text
Lee ROADMAP §4-F8, docs/HIPOTESIS.md y reports/FASE_07.md. Implementa
src/pitcheo/altitud.py: contrafactual por lanzamiento con T, Δ absoluto y relativo
por forma con IC por bootstrap de lanzadores, descomposición de Shapley (Prop. 12),
curva de elasticidad en rejilla, corroboración intra-lanzador con statsmodels
MixedLM, riesgo de HR por forma. Después evalúa H1–H6 exactamente como están
pre-registradas: un solo Benjamini–Hochberg (q=0.10) sobre todas las pruebas
confirmatorias, etiquetas 🟢🟡⚪🔎. Si un resultado contradice la física
(p.ej. β de H1 negativo), NO lo racionalices: D08.md y DETENTE.
reports/FASE_08.md con el Bloque y la tabla de veredictos.
```

**Compuertas:**
- **G8.1** Corroboración: pendiente de $\hat\beta_k$ sobre $\bar\Delta_k$ > 0 con IC sin 0.
- **G8.2** Shapley suma exactamente el total (error numérico < 10⁻⁶).
- **G8.3** H1–H6 evaluadas con la regla pre-registrada, sin cambios.

---

### F9 — Agregación, perfil ideal y recomendaciones

**Modelo:** Sonnet (cálculo) → Opus (interpretación) · **Duración:** 3–4 h

**Proposición 13 (encogimiento bayesiano empírico).** Para lanzador×forma $j$ con media $\bar y_j$ de $n_j$ lanzamientos, varianza intra $\sigma^2$ y entre $\tau^2$ (estimadas por momentos):

$$\hat\theta_j=\mu+B_j(\bar y_j-\mu),\qquad B_j=\frac{\tau^2}{\tau^2+\sigma^2/n_j},\qquad \operatorname{Var}(\theta_j\mid\bar y_j)=B_j\,\frac{\sigma^2}{n_j}.$$

*Demostración:* posterior normal-normal. Domina en error cuadrático medio al estimador sin encoger (James–Stein) cuando hay ≥ 3 grupos. ∎ Da el intervalo creíble que el director deportivo necesita.

**Stuff+ de arsenal:** media de Stuff+ por forma ponderada por uso, con la varianza propagada.

**Proposición 14 (perfil ideal factible).** Sea $\hat p_k$ la densidad de la mezcla gaussiana de F5 para la forma $k$, y $\tau_k$ el cuantil 5 % de $\hat p_k$ sobre los lanzamientos observados. El conjunto $\mathcal C_k=\{\psi:\hat p_k(\psi)\ge\tau_k\}$ contiene por construcción el 95 % empírico de los lanzamientos reales. El perfil ideal resuelve

$$\psi_k^\ast=\arg\max_{\psi\in\mathcal C_k}\ \text{Stuff+}\big(\psi;\rho_{CDMX}\big),$$

un problema **no lineal, no convexo y no diferenciable** (el objetivo es un ensamble de árboles). Se resuelve con evolución diferencial (`scipy.optimize.differential_evolution`) y penalización por salir de $\mathcal C_k$. **Robustez:** se reportan los 25 lanzamientos reales más cercanos a $\psi_k^\ast$ y su Stuff+, para mostrar que el óptimo es alcanzable y no un artefacto del modelo.

**Recomendaciones operativas:**
1. Formas que **ganan** Stuff+ relativo en CDMX, con $\phi_{mov}$ y $\phi_{env}$.
2. Formas que **pierden**, con el aumento de $P(\text{HR}\mid\text{BIP})$.
3. Perfil de prospecto: aplicar $T_{\rho\to\rho_{CDMX}}$ a sus lanzamientos de cualquier parque y reportar Stuff+ proyectado con intervalo y comparables de la liga.

**Prompt (Sonnet → Opus):**

```text
[Sonnet] Lee ROADMAP §4-F9. Implementa src/pitcheo/agregacion.py (Prop. 13,
Stuff+ de arsenal) y src/pitcheo/optimizacion.py (Prop. 14 con
differential_evolution, semilla fija, 25 vecinos reales). Tablas en
reports/FASE_09.md.

[Opus] Redacta docs/RECOMENDACIONES.md: las tres secciones operativas, cada
afirmación con su cifra, su intervalo y su etiqueta de evidencia de F8. Lenguaje
para un pitching coach, no para un estadístico. Ninguna afirmación sin respaldo
numérico.
```

**Compuertas:**
- **G9.1** El óptimo de cada forma está a menos de 1 desviación estándar de algún lanzamiento real.
- **G9.2** Toda recomendación cita su cifra y su etiqueta.

---

### F10 — Dashboard simulador

**Modelo:** Sonnet · **Duración:** 3–4 h

Streamlit local (`app/dashboard.py`):
1. **Simulador:** controles de velocidad, IVB, HB, spin, eje, liberación y extensión → Stuff+ en $\rho_{CDMX}$ y en $\rho_{ref}$ lado a lado, con banda de incertidumbre y $\phi_{mov}$/$\phi_{env}$.
2. **Mapa de movimiento:** IVB × HB coloreado por Stuff+, con flechas de $T$ (ref → CDMX).
3. **Prospecto:** cargar un CSV Trackman de un lanzador → Stuff+ proyectado en CDMX, percentil e intervalo.

**Prompt (Sonnet):**

```text
Lee ROADMAP §4-F10. Implementa app/dashboard.py con las tres vistas usando los
artefactos de artefactos/ y el operador de src/pitcheo/operador.py. Sin datos crudos
embebidos. Prueba de humo en tests/test_dashboard.py con artefactos entrenados sobre
el sintético. scripts/fases/f10.sh genera versiones estáticas (PNG) de cada vista en
docs/figuras/f10/. Arranque local en README: `uv run streamlit run app/dashboard.py`.
reports/FASE_10.md con el Bloque.
```

**Nota de confidencialidad:** los artefactos del modelo se entrenaron con datos bajo NDA y **no se suben** salvo autorización explícita de ISAC.

---

### F11 — Reporte final en GitHub

**Modelo:** Opus (redacción) + Sonnet (figuras) · **Duración:** 3–4 h

| Archivo | Contenido |
|---|---|
| `README.md` | Portada: pregunta, respuesta en una frase, tabla de hallazgos con etiquetas, cómo reproducir |
| `docs/REPORTE_FINAL.md` | Documento técnico de 6–10 páginas (estructura abajo) |
| `docs/MODELO_MATEMATICO.md` | Proposiciones 1–14 con demostraciones |
| `docs/RECOMENDACIONES.md` | Versión para cuerpo técnico |
| `docs/ENTREVISTA.md` | Guion de 10 min: tres decisiones que cambian, con cifra e intervalo |

**Estructura de `REPORTE_FINAL.md`:**
1. La LMB como laboratorio natural de densidad (½ p)
2. Física: descomposición, identificación de ρ por juego, robustez a sensor (1½ p)
3. Variable objetivo: pesos lineales, cadena de conteos, Rao–Blackwell (1 p)
4. Modelos: árbol de desenlaces, neutralidad al conteo, Location+ por integral (1½ p)
5. Escala Stuff+ absoluta y relativa (½ p)
6. Validación: cuatro esquemas, baselines, calibración, fiabilidad (1½ p)
7. Efecto altitud: ΔStuff+ por forma, Shapley, H1–H6 (1½ p)
8. Recomendaciones y perfil ideal (1 p)
9. Alcance y lo que el modelo **no** afirma (½ p)

**Prompt (Opus):**

```text
Lee ROADMAP §4-F11 y todos los reports/FASE_*.md. Redacta los cinco archivos.
Reglas: cada cifra con intervalo y etiqueta de evidencia; solo figuras agregadas
(nunca filas por lanzamiento); sección "Lo que no se afirma" obligatoria (sin
estadio ni clima en el dataset; H5 como supuesto del contrafactual; "Harp Helú" es
una clase de densidad (CDMX y Puebla son físicamente indistinguibles), ADR-005). Sonnet genera las figuras faltantes en
docs/figuras/ con los .json ya subidos (sin datos crudos). Verifica que `git
ls-files` no contenga nada de data/, artefactos/ ni reports/privado/. Rama fase11,
PR, merge a main, tag v1.0.
```

**Compuerta final:** `git ls-files | grep -E "data/|artefactos/|\.parquet"` vacío.

---

## 5. Protocolo de orquestación

**Bloque para el orquestador** (obligatorio al final de cada `reports/FASE_XX.md`):

```markdown
### Bloque para el orquestador — FXX
- Modelo(s) usado(s): Opus / Sonnet
- Compuertas: G.1 ✅ (cifra) | G.2 ❌ (cifra) | ...
- Cifras clave (con IC): ...
- Desviaciones respecto al ROADMAP: ninguna | descripción
- Mejora posible detectada: ninguna | descripción y costo estimado
- Riesgo de empeorar: ninguno | descripción
- Rama / PR / commit de resultados locales: faseXX / #NN / <hash>
- Log: reports/logs/fXX_<fecha>.log
```

**Cuándo se escala al orquestador** (Claude Code se detiene y escribe `docs/discrepancias/DXX.md`):

| Tipo | Disparador |
|---|---|
| A — Compuerta | Cualquier compuerta falla |
| B — Física | Un resultado contradice la física (signo de β en H1, carry < 1, etc.) |
| C — Mejora | Claude Code detecta una alternativa mejor que lo especificado |
| D — Riesgo | Un cambio pedido podría empeorar validez o reproducibilidad |

**Reglas:**
- Claude Code **no** modifica `ROADMAP.md` ni `docs/HIPOTESIS.md`. Solo el orquestador, con nueva versión, que Rodrigo sube directo a `main`.
- Nada se mergea a `main` sin una corrida local con datos reales y su reporte, salvo F1.
- Las decisiones del orquestador se registran como ADR en `docs/DECISIONES.md`.
- Un hallazgo no pre-registrado se reporta, pero siempre con etiqueta 🔎.

---

## 6. Registro de riesgos

| Riesgo | Probabilidad | Impacto | Detección | Mitigación |
|---|---|---|---|---|
| Cubetas de altitud no ordenadas como se supone | Media | Alto | G2.2 | Usar $\hat\rho_g$ continua y no la etiqueta |
| *Extreme* sin una clase de densidad de ~2 200 m distinguible | Media | Medio | G2.2(c) | $\rho_{CDMX}$ por barométrica relativa a la referencia; se reporta como supuesto |
| Valores categóricos nuevos en datos futuros | Media | Bajo | G0.5 | Fallo explícito "sin regla", nunca asignación silenciosa |
| Medias entradas de 2 outs sesgan los pesos lineales | Media | Medio | ADR-012 | Criterio A principal, B sensibilidad; escalar si difieren |
| Banderas `is_*` inconsistentes con `PitchCall` | Confirmada | Bajo | ADR-011 | Árbol desde `pitch_call_h` |
| Turnos perdidos (L), más si son ponche | Por medir | Medio | G0.9 (Prop. 16) | ω por cubeta con $\pi\in\{0,1\}$ solo si G0.9 ≠ U |
| Pérdida de datos distinta por cubeta | Por medir | **Alto** | G0.8′ (Prop. 17) | Intervalos de Imbens–Manski en F8; parar si el ancho supera el IC95 |
| `OutsOnPlay` no cuenta dobles matanzas ni K + robo atrapado | **Probable** (§1.4) | Medio | G0.9, corroboraciones (a)–(e) | Modelo C en F4.1 con regresor $u_h$; nunca usar `OutsOnPlay` como verdad de outs |
| Reloj y signos de los 9P mal supuestos | Confirmada (corregida) | Alto | G0.7 | ADR-014 antes de F2 |
| Sesgo de sensor por parque | Media | Alto | G2.3 (Prop. 3) | Sobreidentificación; acotar sesgo |
| Convención del polinomio distinta | Media | Medio | I3 | Ajustar fórmula de $t^\ast$; ADR |
| Pocos lanzadores en varias cubetas | Media | Alto | F0 | Efectos aleatorios en vez de fijos; ampliar IC |
| Falla H5 (bateador responde distinto en altura) | Baja | Alto | G7.3 | Entorno como feature en N1–N4; contrafactual sin Prop. 5 |
| Medias entradas incompletas por huecos de Trackman | Media | Medio | I7 | Filtrar a completas; sensibilidad |
| Fuga de ubicación vía VAA o EffectiveVelo | Alta si no se atiende | Alto | G5.1 | nVAA, $v_{perc}$ |
| Renormalizar dentro de CDMX y borrar el efecto | Alta si no se atiende | Alto | Prop. 10 | Escala absoluta y relativa por separado |
| Datos bajo NDA en el repo público | Baja | Crítico | Compuerta final | `.gitignore` + verificación `git ls-files` |
| Los tres archivos crudos no son idénticos | Baja | Alto | G00.2 | El orquestador elige fuente; ADR |
| `.pkl` incompatible o inseguro | Media | Bajo | F0.0 | Parquet canónico; el `.pkl` solo se usa para la verificación |
| El código pasa con el sintético y truena con datos reales | Alta | Medio | Corrida local | Prompt de error §0.5: primero se reproduce el caso en el sintético |
| Filtración de datos por logs o reportes | Baja | Crítico | Revisión §0.4 | Logs solo con formas y agregados; tablas por lanzador en `reports/privado/` |
| LightGBM sin wheel para Python 3.13/3.14 de Arch | Media | Bajo | F0 | `uv python pin 3.12` |
