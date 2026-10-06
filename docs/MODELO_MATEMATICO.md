# Modelo matemático

Proposiciones 1-14 con demostraciones. Cada fase con diseño de Opus agrega su
sección antes de implementar (ROADMAP). F0.0 solo deja el marcador.

---

# F2 — Densidad del aire por juego desde la trayectoria

Diseño (Opus, Prompt 1 de §4-F2). **No implementa**: la implementación es el Prompt 2 (Sonnet).
Objetivo: estimar $\hat\rho_g$ por juego con solo la física del lanzamiento, validarla contra la
barométrica (§2) y descartar sesgo de sensor. Núcleo del proyecto (ADR-001).

## F2.0 Sistema de coordenadas, unidades y constantes

**Ejes Trackman (§2 y diccionario).** Origen en la **punta del plato**; $x$ horizontal (lado),
$y$ hacia el **montículo** (positivo hacia el lanzador), $z$ **hacia arriba**. `y0` y `z0` se miden
desde la punta del plato; `x0` desde el centro de la goma (un desplazamiento lateral constante que
no afecta velocidades ni aceleraciones). La trayectoria canónica es la de los **9P**
$\mathbf r(t)=\mathbf r_0+\mathbf v_0 t+\tfrac12\mathbf a t^2$ con
$\mathbf r_0=(x_0,y_0,z_0)$, $\mathbf v_0=(v_{x0},v_{y0},v_{z0})$,
$\mathbf a=(a_{x0},a_{y0},a_{z0})$ (ADR-010 enmienda: los `PitchTrajectory*` son estos mismos 9P en
ejes permutados; aquí se usan directamente las columnas `x0…az0`). Como el lanzamiento va hacia el
plato, $v_{y0}<0$.

**Marco temporal (ADR-014, ya medido en F0).** El reloj de los 9P arranca en $y_0=50$ ft. Por
lanzamiento:

- $t_s=\dfrac{c^X_{1}-v_{y0}}{a_{y0}}$ (origen del polinomio = liberación), mediana $-0.0363$ s;
- $t_p$ = raíz **positiva pequeña** de $y(t_p)=y_p$ con $y_p=17/12$ ft y la trayectoria 9P
  ($y(t)=y_0+v_{y0}t+\tfrac12 a_{y0}t^2$);
- signo de ubicación: `PlateLocSide` $=-\,x(t_p)$ (ADR-014, $s=-1$);
- **punto medio** $t_m=\tfrac12(t_s+t_p)$ (Prop. 1).

Como $t_s<0<t_p$, $t_m$ está entre la liberación y el plato; $\Delta:=t_p-t_s=$ `ZoneTime`
(verificado en F0, $|\text{ZoneTime}-(t_p-t_s)|$ mediana $0.03$ ms).

**Conversión a SI** (toda la física se hace en SI; las columnas vienen en unidades imperiales):

| magnitud | columna | factor a SI |
|---|---|---|
| posición | `x0,y0,z0` (ft) | $\times0.3048$ m |
| velocidad | `vx0,vy0,vz0` (ft/s) | $\times0.3048$ m/s |
| aceleración | `ax0,ay0,az0` (ft/s²) | $\times0.3048$ m/s² |
| rapidez | `RelSpeed,ZoneSpeed` (mph) | $\times0.44704$ m/s |
| break/pfx | `*Break,pfx*` (in) | $\times0.0254$ m |
| giro | `SpinRate` (rpm) | $\times2\pi/60=0.104720$ rad/s |
| eje de giro | `SpinAxis` (°) | $\times\pi/180$ rad |

**Constantes (§2).** $m=0.145$ kg, $r=0.0368$ m, $A=\pi r^2=4.254\times10^{-3}$ m²,
$2m/A=68.2$ kg·m⁻², $\mathbf g=(0,0,-9.80665)$ m/s² (= $-32.174$ ft/s² en $z$),
$\kappa(\rho)=\rho A/(2m)$, factor de giro $S=r\omega/\lVert\mathbf v\rVert$ con
$\omega=2\pi\cdot\text{SpinRate}/60$.

## F2.1 Proposición 1 — descomposición arrastre–Magnus

**Modelo físico.** Con arrastre a lo largo de $-\mathbf v$ y Magnus perpendicular a $\mathbf v$,

$$\ddot{\mathbf r}=\mathbf g-\kappa C_D\lVert\mathbf v\rVert\mathbf v+\kappa C_L\lVert\mathbf v\rVert^2\hat{\mathbf n},\qquad \hat{\mathbf n}=\frac{\boldsymbol\omega_T\times\mathbf v}{\lVert\boldsymbol\omega_T\times\mathbf v\rVert}\perp\mathbf v .$$

**Afirmación.** Con $\tilde{\mathbf a}=\mathbf a-\mathbf g$ (aceleración aerodinámica; se **resta la
gravedad verdadera**, porque la $\mathbf a$ medida de los 9P la incluye) y la velocidad representativa
$\bar{\mathbf v}=\mathbf v_0+\mathbf a\,t_m$,

$$\rho C_D=-\frac{2m}{A}\,\frac{\tilde{\mathbf a}\cdot\hat{\bar{\mathbf v}}}{\lVert\bar{\mathbf v}\rVert^2},\qquad \rho C_L=\frac{2m}{A}\,\frac{\lVert\tilde{\mathbf a}-(\tilde{\mathbf a}\cdot\hat{\bar{\mathbf v}})\hat{\bar{\mathbf v}}\rVert}{\lVert\bar{\mathbf v}\rVert^2}.$$

**Demostración.** $\tilde{\mathbf a}=-\kappa C_D\lVert\mathbf v\rVert\mathbf v+\kappa C_L\lVert\mathbf v\rVert^2\hat{\mathbf n}$.
Proyectar sobre $\hat{\mathbf v}$ anula el Magnus ($\hat{\mathbf n}\perp\mathbf v$):
$\tilde{\mathbf a}\cdot\hat{\mathbf v}=-\kappa C_D\lVert\mathbf v\rVert^2$. El residuo perpendicular
$\tilde{\mathbf a}-(\tilde{\mathbf a}\cdot\hat{\mathbf v})\hat{\mathbf v}=\kappa C_L\lVert\mathbf v\rVert^2\hat{\mathbf n}$,
de norma $\kappa C_L\lVert\mathbf v\rVert^2$. Como $\kappa=\rho A/(2m)$, multiplicar por $2m/A$
despeja $\rho C_D$ y $\rho C_L$. Se evalúa en $\bar{\mathbf v}=\mathbf v(t_m)$ como velocidad
representativa de un vuelo con $\lVert\mathbf v\rVert$ variable. $\blacksquare$

**Por qué $\rho C$ y no $\rho$ a secas.** La trayectoria solo identifica el producto $\rho C_D$ (y
$\rho C_L$): no se puede separar densidad de coeficiente con un lanzamiento. La separación la hace la
Prop. 2′: $C_D$ y $C_L$ dependen de $(S,k,h)$ —misma pelota, misma física— y $\rho$ depende del juego,
así que el efecto fijo de juego aísla $\log\rho_g$ salvo una constante.

## F2.2 Error de la regla del punto medio, como función de $\Delta=t_p-t_s$

El ajuste 9P da una **aceleración constante** $\mathbf a$; la real escala con $\lVert\mathbf v\rVert^2$,
que decae en vuelo. A primer orden, el ajuste por mínimos cuadrados de un trayecto con aceleración
que varía lentamente devuelve la $\mathbf a$ **promedio temporal** sobre la ventana, de modo que
$\tilde{\mathbf a}_{\text{9P}}\approx\langle\tilde{\mathbf a}(t)\rangle$. La identidad de arrastre
vale **instante a instante**: $\tilde{\mathbf a}(t)\cdot\hat{\mathbf v}=-\kappa C_D\lVert\mathbf v(t)\rVert^2$.
Promediando (con $\kappa C_D$ casi constante y $\hat{\mathbf v}$ casi fijo),
$\langle\tilde{\mathbf a}\cdot\hat{\mathbf v}\rangle=-\kappa C_D\langle\lVert\mathbf v\rVert^2\rangle$,
pero evaluamos con $\lVert\bar{\mathbf v}\rVert^2=\lVert\mathbf v(t_m)\rVert^2$. El error relativo del
estimador es el de aproximar el promedio por el valor en el punto medio.

Sea $\varphi(t)=\lVert\mathbf v(t)\rVert^2$. La **regla del punto medio** para el promedio sobre
$[t_s,t_p]$:

$$\langle\varphi\rangle=\frac1\Delta\int_{t_s}^{t_p}\varphi\,dt=\varphi(t_m)+\frac{\Delta^2}{24}\,\varphi''(t_m)+O(\Delta^4),$$

de modo que el error relativo es

$$\varepsilon_{\text{mid}}(\Delta)=\frac{\langle\varphi\rangle-\varphi(t_m)}{\varphi(t_m)}=\frac{\Delta^2}{24}\,\frac{\varphi''(t_m)}{\varphi(t_m)}+O(\Delta^4).$$

**Cota analítica.** La deceleración por arrastre domina $\varphi'$:
$\varphi'=2\,\mathbf v\!\cdot\!\mathbf a\approx-2\kappa C_D\lVert\mathbf v\rVert^3$, luego
$\dfrac{d\lVert\mathbf v\rVert}{dt}\approx-\kappa C_D\lVert\mathbf v\rVert^2$ y
$\varphi''\approx 6(\kappa C_D)^2\lVert\mathbf v\rVert^4$. Entonces
$\varphi''/\varphi\approx 6(\kappa C_D\lVert\mathbf v\rVert)^2$ y

$$\varepsilon_{\text{mid}}(\Delta)\approx\frac{\Delta^2}{4}\,(\kappa C_D\lVert\mathbf v\rVert)^2=\frac{s^2}{4},\qquad s:=\kappa C_D\lVert\mathbf v\rVert\,\Delta\approx\frac{\lVert\mathbf v(t_s)\rVert-\lVert\mathbf v(t_p)\rVert}{\lVert\mathbf v(t_s)\rVert},$$

donde $s$ es la **fracción de rapidez perdida** en el vuelo. El $\Delta^2$ se cancela contra
$(s/\Delta)^2$: el error es **de segundo orden en $s$** y, a ese orden, no depende de $\Delta$ por
separado. Con los números del dataset ($\kappa C_D\lVert\mathbf v\rVert\approx0.25$ s⁻¹,
$\Delta\approx0.40$ s $\Rightarrow s\approx0.10$) sale $\varepsilon_{\text{mid}}\approx0.25\%$; en el
peor caso (lanzamientos lentos/largos, $s\le0.20$, lo que §4-F2 llama "15–20 % de caída")
$\varepsilon_{\text{mid}}\le s^2/4\le1\%$, justo el umbral de G2.1.

**Dependencia en $\rho$ y sesgo diferencial (corrección §1.6(4)).** Como $s=\kappa C_D\lVert\mathbf v\rVert\Delta$
y $\kappa=\rho A/2m$, se tiene $s\propto\rho$ y por tanto $\varepsilon_{\text{mid}}\propto\rho^2$. La parte
que varía con la forma/rapidez **a $\rho$ fija** entra en $f_D$, pero la parte que **varía con $\rho$ NO la
absorbe $f_D$** (que es común a todos los juegos, independiente de la densidad): un $f_D$ sin densidad no puede
capturar un término proporcional a $\rho$, así que ese pedazo sí llega a $\delta_g$. Lo que de verdad sesga a
$\delta_g$ —identificado de **diferencias** de densidad— es el **diferencial** entre cubetas:

$$\varepsilon_{\text{mid}}(\rho_0)-\varepsilon_{\text{mid}}(0.76\rho_0)=\frac{s_0^2}{4}\,(1-0.76^2)\approx\frac{s_0^2}{4}\cdot0.42\approx0.001\ \text{en }\log\rho\quad(s_0\approx0.10),$$

despreciable frente a la señal de 0.27 y bajo la resolución 0.01 de G2.2(c). La sintética lo verifica
(F2.5). Términos de orden superior que la sintética también cuantifica: la rotación de $\hat{\mathbf v}$
(el lanzamiento se curva) y la proyección $\mathbf g\cdot\hat{\mathbf v}$ (pequeña, lanzamiento casi
horizontal; Prop. 3′).

## F2.3 Proposición 2′ — dos efectos fijos (juego + lanzador×forma) y diseño del estimador

(Sustituye a la Prop. 2 original; revisión del orquestador §1.6(2).) Con $y^D_i=\log(\rho C_D)_i$,

$$y^D_i=\delta_{g(i)}+\alpha_{j(i),k(i)}+f_D(S_i,k_i,h_i,\text{year}_i)+\eta_i,\qquad\mathbb E[\eta_i\mid\cdot]=0,$$

con **dos** efectos fijos: juego $\delta_g$ y lanzador×forma $\alpha_{j,k}$, más $f_D$ común (misma pelota,
misma física). **Por qué el segundo efecto fijo:** sin $\alpha_{j,k}$, el $C_D$ medio del *staff* local carga
en el parque (los lanzadores de casa lanzan más en su parque), con un sesgo de orden $0.01$ en $\log\rho$ —
**igual a la resolución que pide G2.2(c)**. El efecto fijo de lanzador×forma lo elimina.

$\delta_g-\delta_{g'}=\log(\rho_g/\rho_{g'})$ está identificado dentro del **conjunto conectado** del grafo
bipartito juegos–(lanzador×forma) (Abowd–Kramarz–Margolis 1999, AKM): dos juegos son comparables si una
cadena de lanzadores×forma compartidos los une. F2 **reporta el tamaño del componente conectado** (cuántos
juegos y lanzador×forma entran); los juegos fuera del gigante no tienen $\delta_g$ identificado y van a 🔎. El
nivel absoluto sigue sin identificarse (cualquier constante pasa de $\delta$ a $f_D$), de ahí la
normalización. **Demostración:** modelo AKM de dos efectos fijos con covariable flexible común; las
diferencias de efectos fijos del mismo factor son estimables en el componente conectado del grafo bipartito,
donde la matriz de diseño proyectada tiene rango completo. $\blacksquare$

**Diseño del estimador (lo que implementará Sonnet).** $y^D_i$ sobre dummies de juego $\{\delta_g\}$ + dummies
de lanzador×forma $\{\alpha_{j,k}\}$ + base B-spline de $S$ **por estrato** $(k,h,\text{year})$ (nudos fijos
sobre el rango agrupado del estrato). Como hay miles de dummies en los dos factores, se estima por
**proyecciones alternadas** (Guimarães–Portugal 2010): se barren en turnos las medias por juego y por
lanzador×forma (al estilo de la transformación "within" iterada) hasta converger, con $f_D$ parcializado. Lo
mismo con $y^L_i=\log(\rho C_L)_i$ para $\delta^L_g$.

**Normalización.** $\bar\delta_{\text{No Altitude}}:=0$ calculada **solo** sobre los juegos cuya
cubeta imputada (ADR-005) es *No Altitude*. Entonces $\hat\rho_g/\rho_{ref}=e^{\hat\delta_g}$. No se
normaliza a una barométrica absoluta porque las cubetas no traen altitud numérica.

**Los 10 juegos sin cubeta** (3 020 lanzamientos, FASE_00.md). Se les **ajusta** su $\delta_g$ como a
cualquier otro juego (entran en $f_D$ y aportan a su estimación), pero quedan **fuera de la
normalización** (no son referencia) y **fuera de las medias por cubeta y de las compuertas
confirmatorias** G2.2. Uso 🔎: se predice su cubeta a partir de $\hat\delta_g$ (¿cae en el rango de
*No/Medium/Extreme*?) como validación exploratoria del método, nunca como insumo de H1–H6.

**Soporte común / condición de rango — qué hacer si falla.** Para cada estrato $(k,h,\text{year})$:

1. Se fija el vector de nudos de la spline sobre el rango de $S$ **agrupado** del estrato.
2. Un $\delta_g$ solo es identificable si las filas del juego $g$ comparten región de $(S,k,h)$ con
   otros juegos de **otra** cubeta (si no, $\delta_g$ y $f_D$ se confunden en ese tramo).
3. **Diagnóstico de rango:** tras parcializar $f_D$, se mide el número de condición de $X^\top X$ y,
   por juego, el **$n$ efectivo** = lanzamientos que caen en regiones de $S$ compartidas con $\ge1$
   juego de otra cubeta.
4. **Fallback por coarsening** cuando un estrato tiene soporte en un solo juego o la spline no se
   separa del dummy, en este orden (§1.6(5)): menos nudos → spline lineal → **fundir forma $k$ en
   `familia`** (ADR-002) → marcar el juego como baja confianza. **Nunca se elimina `year`**, porque la
   pelota cambia de arrastre entre temporadas y colapsar años mezclaría dos $f_D$ distintos. El coarsening
   aplicado se **registra** en el reporte.
5. Un juego con $n$ efectivo $< n_{\min}$ (umbral en `config/default.yaml`, propuesta $n_{\min}=30$)
   o con número de condición sobre el tope se marca **baja confianza**: sale de las medias
   confirmatorias y se reporta 🔎.

**Estimador de $\sigma_\eta$.** Desviación estándar residual de la regresión de dos efectos fijos:

$$\hat\sigma_\eta^2=\frac{1}{N-p}\sum_i\hat\eta_i^2,\qquad p=(\#\text{juegos}-1)+\#\{\alpha_{j,k}\}_{\text{conectados}}+\sum_{\text{estratos}}\text{df}_{\text{spline}},$$

($\#\text{juegos}-1$ por la normalización; $\#\{\alpha_{j,k}\}$ cuenta los efectos de lanzador×forma del
componente conectado). Es el $\sigma_\eta$ que pide G2.4 y la escala de los SE.

**Errores estándar (§1.6(3)).**

- **Para $\delta_g$:** corrección **CR2** (Bell–McCaffrey 2002) con conglomerados = **lanzador dentro del
  juego**. Como hay pocos conglomerados por juego (~9 lanzadores), el estimador robusto estándar (CR0)
  subestima; CR2 ajusta el apalancamiento de cada conglomerado y da la referencia con grados de libertad de
  Satterthwaite. El SE ingenuo $\hat\sigma_\eta/\sqrt{n_g}$ supone independencia y se reporta solo de
  contraste. **G2.4** usa la **mediana** del SE **CR2** sobre los juegos, y exige $<0.03$.
- **Para los contrastes de medias por cubeta y la regresión de Deming:** **agrupamiento doble
  juego × lanzador** (Cameron–Gelbach–Miller 2011), porque un lanzador aparece en varios juegos y un juego
  tiene varios lanzadores; el SE de dos vías suma los dos agrupamientos y resta la intersección.

*Precisión esperada (§4-F2):* con ~250 lanzamientos/juego y $\sigma_\eta\approx0.15$, el SE ingenuo
$\approx0.01$; el CR2 será algo mayor según la correlación intra-lanzador, y debe seguir bajo 0.03 contra
una señal de 0.27.

## F2.4 Proposición 3′ — robustez a sesgos de calibración (escala y reloj unificados)

(Sustituye a la Prop. 3 original; revisión del orquestador §1.6(1). La versión anterior afirmaba por error
que la escala $\lambda$ no la detecta Deming; sí la detecta.) Con escala espacial $\lambda_g$ y reloj
$\tau_g$ por parque, lo **medido** es $\tilde{\mathbf r}=\lambda\mathbf r$ en tiempos estirados por $\tau$,
de modo que $\tilde{\mathbf v}=(\lambda/\tau)\mathbf v$ y $\tilde{\mathbf a}=(\lambda/\tau^2)\mathbf a_{\text{full}}$,
con $\mathbf a_{\text{full}}=\mathbf a_{\text{aero}}+\mathbf g$. Al restar la **gravedad verdadera**,

$$\tilde{\mathbf a}-\mathbf g=\frac{\lambda}{\tau^2}\,\mathbf a_{\text{aero}}+c_g\,\mathbf g,\qquad c_g=\frac{\lambda_g}{\tau_g^2}-1 .$$

**Consecuencias.**

- **(a)** El cociente aerodinámico $\mathbf a_{\text{aero}}/\lVert\mathbf v\rVert^2$ escala por $1/\lambda$
  (el $\tau$ se cancela entre $\tilde{\mathbf a}$ y $\lVert\tilde{\mathbf v}\rVert^2$), así que
  $\delta^D_g=\log\rho_g-\log\lambda_g$: **el reloj no entra en el canal de arrastre.**
- **(b)** Tanto la escala como el reloj dejan el **mismo** residuo $c_g\,\mathbf g$, casi perpendicular a
  $\mathbf v$ (gravedad vertical, lanzamiento casi horizontal). Ese residuo carga en el **canal de
  sustentación**, así que $\delta^L_g-\delta^D_g$ estima $c_g=\lambda_g/\tau_g^2-1$: la **combinación**,
  sin poder separar escala de reloj. En particular, una escala pura ($\tau=1$) da $c_g=\lambda-1\neq0$, así
  que **$\lambda=1.02$ SÍ diverge en Deming** (mi versión anterior lo negaba: olvidaba que la gravedad
  verdadera se resta sin escalar, dejando el término $(\lambda-1)\mathbf g$).
- **(c)** Un sesgo de 2 % mueve $\delta$ un 2 %, **un orden bajo la señal** ($|\log0.762|=0.27$).

**Mapa corregido "sesgo → compuerta".** El orden/bandas de G2.2 se conservan ante un sesgo de 2 % (solo
desplaza $\delta$ un 2 %), pero **G2.3 (Deming) detecta tanto $\lambda$ como $\tau$**, porque ambos dejan
$c_g\neq0$: $\delta^L-\delta^D\neq0$. Un sesgo de sensor no puede fabricar el efecto altitud y deja huella
en la sobreidentificación. $\blacksquare$

**Detector adicional por $\hat{\mathbf e}=\hat{\mathbf v}\times\hat{\mathbf n}_{\text{spin}}$
(§1.6(1)).** Un tercer eje ortogonal a $\hat{\mathbf v}$ y a la dirección de giro $\hat{\mathbf n}_{\text{spin}}$
(de `SpinAxis`). En ese eje el Magnus verdadero no tiene componente, así que

$$\tilde{\mathbf a}\cdot\hat{\mathbf e}_i=c_g\,(\mathbf g\cdot\hat{\mathbf e}_i)+\beta_{j,k}+\epsilon_i,$$

donde $\beta_{j,k}$ absorbe la estela por costuras y el desajuste de eje del lanzador; la regresión de
$\tilde{\mathbf a}\cdot\hat{\mathbf e}$ sobre $\mathbf g\cdot\hat{\mathbf e}$ (con efecto fijo lanzador×forma)
da $\hat c_g$ **por juego**, que separa el residuo de calibración del Magnus y complementa a Deming.

**Condición: `SpinAxis` debe ser MEDIDO, no inferido del movimiento.** Si el eje se derivó del propio
break, $\hat{\mathbf n}_{\text{spin}}$ es función de $\tilde{\mathbf a}$ y la ecuación es circular. Cómo se
verifica con los datos: (i) regresar `SpinAxis` (y `SpinRate`) sobre las columnas de movimiento
(`HorzBreak`, `InducedVertBreak`, `VertBreak`, `pfxx`, `pfxz`, `RelSpeed`); si el $R^2\approx1$ (residuo al
nivel del redondeo), el eje es inferido; (ii) medir $\operatorname{Var}(\tilde{\mathbf a}\cdot\hat{\mathbf e})$
dentro de cada lanzador×forma: si es $\approx0$ (piso de ruido), el eje no aporta información independiente y
también es inferido. Si cualquiera de las dos lo marca inferido, se **declara así en el reporte** y el único
detector de calibración es G2.3 (Deming).

## F2.5 Prueba sintética (a) — diseño

**Generación (verdad conocida).** Integrar el modelo físico con `scipy.integrate.solve_ivp`
(método **DOP853**, `rtol=1e-10`, `atol=1e-12`) desde el estado de liberación hasta $y=y_p$, para
**5 000 lanzamientos** repartidos en 3 niveles de densidad conocida $\rho\in\{1.00,0.82,0.76\}\rho_0$
(cubeta baja / media / extrema) y un abanico realista de formas: $C_D\in[0.30,0.40]$ dependiente de
Reynolds, $C_L=C_L(S)$ con factor de giro $S\in[0.15,0.25]$ ($\omega$ de `SpinRate`), velocidades de
liberación 70–100 mph, ejes de giro por forma. La densidad entra **solo** por
$\kappa=\rho A/(2m)$; $C_D,C_L$ son propiedades de la pelota/forma, no del parque.

**Medición simulada.** Muestrear posiciones a la tasa de Trackman sobre la ventana de vuelo, añadir
**ruido de posición realista** (gaussiano, $\sigma_{\text{pos}}\approx0.015$ m $\approx0.5$ in por eje)
y **reajustar un modelo 9P de aceleración constante por mínimos cuadrados** sobre esas posiciones.
Recuperar $\rho C_D,\rho C_L$ con la Prop. 1 evaluada en $t_m$ y estimar $\delta_g$ con el estimador de la
Prop. 2′. Además de la física del lanzamiento, sembrar un **efecto de lanzador** $\alpha_j$ con desviación
estándar $0.05$ en $\log C_D$ y **asignar cada *staff* a su parque local** (correlación lanzador–parque),
para poder exhibir el sesgo de confusión de la Prop. 2′. La sintética **corre aquí** (sin datos reales).

**Escenarios y qué compuerta responde a cada sesgo** (corregido por §1.6(1) y (6)):

| escenario | qué se inyecta | efecto esperado | compuerta que responde |
|---|---|---|---|
| base + ruido | $\sigma_{\text{pos}}$ realista | recuperación de $\rho$ con error $<1\%$; fija $\sigma_\eta$ y el SE de $\delta_g$ | **G2.1** y **G2.4** |
| *staff* local sin $\alpha_{j,k}$ | $\alpha_j$ (SD $0.05$ en $\log C_D$) + lanzadores atados a su parque | el $C_D$ del *staff* carga en $\delta_g$: sesgo $\sim0.01$ en $\log\rho$ | **se ve el sesgo** con el modelo de un solo efecto fijo |
| *staff* local con $\alpha_{j,k}$ | igual, pero estimando la **Prop. 2′** (juego + lanzador×forma) | el sesgo **desaparece** | el segundo efecto fijo lo corrige |
| escala $\lambda=1.02$, $\tau=1$ | $\tilde{\mathbf r}=\lambda\mathbf r$ | $c_g=\lambda-1=+0.02$; $\delta^L-\delta^D$ diverge; $\hat c_g\approx+0.02$ | **G2.3** (Deming) y el detector $\hat{\mathbf e}$ |
| reloj $\tau=1.01$, $\lambda=1$ | tiempos estirados por $\tau$ | $c_g=1/\tau^2-1\approx-0.0197$; $\delta^L-\delta^D$ diverge; $\hat c_g\approx-0.02$ | **G2.3** (Deming) y el detector $\hat{\mathbf e}$ |

Ambos sesgos de calibración (la escala y el reloj) **deben detectarse en G2.3** con $\hat c_g\approx\pm0.02$:
el punto clave de la corrección §1.6(1) es que la escala ya **no** pasa desapercibida.

La sintética reporta, por escenario: error de recuperación de $\rho$ por nivel; $\hat\sigma_\eta$ y el SE
CR2 de $\hat\delta_g$; la pendiente/intercepto de Deming; $\hat c_g$ del detector $\hat{\mathbf e}$ y la
fracción de la discrepancia $\delta^L-\delta^D$ en la vertical; y, para el *staff* local, $\delta_g$ con y
sin $\alpha_{j,k}$. También cuantifica $\varepsilon_{\text{mid}}$ y su **diferencial** entre densidades
($\approx0.001$, F2.2), confirmando que es despreciable aunque $f_D$ no lo absorba.

## F2.6 Prueba de Deming $\delta^D$ vs $\delta^L$ (c)

Bajo el modelo, $\delta^D_g=\delta^L_g$ (sobreidentificación), porque $\delta^L-\delta^D=c_g=\lambda_g/\tau_g^2-1=0$
sin sesgo de calibración (Prop. 3′). Ambos son ruidosos (errores-en-variables), así que se usa **regresión de
Deming** con razón de varianzas
$\lambda_{\text{Dem}}=\operatorname{Var}(\text{err }\delta^L)/\operatorname{Var}(\text{err }\delta^D)$
estimada de los SE por juego (F2.3). La inferencia de la pendiente usa **agrupamiento doble juego × lanzador**
(§1.6(3)). La hipótesis física es **pendiente 1, intercepto 0**. **G2.3** aprueba si la pendiente
$\in[0.85,1.15]$. Una desviación, con la discrepancia cargada en la vertical, es la firma de un sesgo de
calibración —escala o reloj, que la Prop. 3′ no separa— y, junto con $\hat c_g$ del detector $\hat{\mathbf e}$,
va al orquestador.

## F2.7 Mapa a las compuertas de F2

| compuerta | criterio (§4-F2) | de dónde sale |
|---|---|---|
| **G2.1** | error sintético de recuperación de $\rho<1\%$ | F2.5 base; cota teórica $\varepsilon_{\text{mid}}\le s^2/4$ (F2.2) |
| **G2.2** | orden $\bar\delta_{\text{No}}>\bar\delta_{\text{Medium}}>\bar\delta_{\text{Extreme}}$; $\bar\delta_{\text{Extreme}}\in[-0.30,-0.15]$; componente densa de *Extreme* en $[-0.32,-0.20]$ | F2.3 (medias por cubeta, parques latentes GMM+BIC 🔎) |
| **G2.3** | Deming $\delta^L$ sobre $\delta^D$: pendiente $\in[0.85,1.15]$; detecta escala **y** reloj ($c_g\neq0$) | F2.6, Prop. 3′; $\hat c_g$ del detector $\hat{\mathbf e}$ |
| **G2.4** | $\sigma_\eta$ medida y SE mediano **CR2** de $\hat\delta_g<0.03$ | F2.3 (CR2, lanzador dentro del juego) |

**Si G2.2 falla con G2.3 aprobada:** las cubetas no corresponden a la altitud supuesta. **Si G2.3
falla:** sesgo de calibración (escala o reloj, $c_g\neq0$; Prop. 3′). Ambos van al orquestador.

**Ningún outcome entra en F2:** solo física por lanzamiento ($\mathbf r_0,\mathbf v_0,\mathbf a$,
`SpinRate`, `SpinAxis`, forma, mano, año). Los `*_anon_id` entran como **efecto fijo lanzador×forma**
(Prop. 2′), para agrupar los SE (CR2) y para validar; nunca como *feature* de un modelo de outcomes.
