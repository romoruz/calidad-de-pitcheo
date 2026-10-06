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
Prop. 2: $C_D$ y $C_L$ dependen de $(S,k,h)$ —misma pelota, misma física— y $\rho$ depende del juego,
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

**Lo que salva a $\hat\rho_g$.** $\varepsilon_{\text{mid}}$ es una función **suave de la rapidez**,
que correlaciona con la forma $k$. Como $f_D(S,k,h,\text{year})$ de la Prop. 2 es una función común
flexible de forma y giro, el sesgo del punto medio se **absorbe en $f_D$** y casi no toca al efecto
de juego $\delta_g$, siempre que la distribución de rapidez por forma sea parecida entre juegos
(la condición de soporte común de la Prop. 2). Términos de orden superior que descarto aquí y que la
sintética debe cuantificar: la rotación de $\hat{\mathbf v}$ (el lanzamiento se curva) y la
proyección $\mathbf g\cdot\hat{\mathbf v}$ (pequeña, lanzamiento casi horizontal; Prop. 3b).

## F2.3 Proposición 2 — identificación de $\rho_g$ y diseño del estimador

Con $y^D_i=\log(\rho C_D)_i$,

$$y^D_i=\delta_{g(i)}+f_D(S_i,k_i,h_i,\text{year}_i)+\eta_i,\qquad\mathbb E[\eta_i\mid\cdot]=0,$$

$f_D$ común a todos los juegos (misma pelota, misma física). Bajo **soporte común** de $(S,k,h)$
entre juegos, $\delta_g-\delta_{g'}=\log(\rho_g/\rho_{g'})$ está identificado; el nivel absoluto no
(cualquier constante pasa de $\delta$ a $f_D$), de ahí la normalización. **Demostración:** efectos
fijos con covariable flexible común; la diferencia de dos efectos fijos es estimable si la matriz de
los dummies, proyectada fuera del espacio de $f_D$, tiene rango completo, lo que da el soporte
común. $\blacksquare$

**Diseño del estimador (lo que implementará Sonnet).** OLS de $y^D_i$ sobre:
dummies de juego $\{\delta_g\}$ + base B-spline de $S$ **por estrato** $(k,h,\text{year})$ (tensor
estratificado: una spline de $S$ con nudos fijos sobre el rango agrupado de cada estrato). Lo mismo
con $y^L_i=\log(\rho C_L)_i$ para $\delta^L_g$.

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
   separa del dummy: se reduce la spline (menos nudos → lineal → media única) y, si aún falla, se
   funde el estrato a un nivel más grueso: quitar `year`, luego fundir forma $k$ en `familia`
   (ADR-002), hasta recuperar soporte común. El coarsening aplicado se **registra** en el reporte.
5. Un juego con $n$ efectivo $< n_{\min}$ (umbral en `config/default.yaml`, propuesta $n_{\min}=30$)
   o con número de condición sobre el tope se marca **baja confianza**: sale de las medias
   confirmatorias y se reporta 🔎.

**Estimador de $\sigma_\eta$.** Desviación estándar residual de la regresión de efectos fijos:

$$\hat\sigma_\eta^2=\frac{1}{N-p}\sum_i\hat\eta_i^2,\qquad p=(\#\text{juegos}-1)+\sum_{\text{estratos}}\text{df}_{\text{spline}},$$

($\#\text{juegos}-1$ por la normalización). Es el $\sigma_\eta$ que pide G2.4 y la escala de los SE.

**SE de $\hat\delta_g$ con agrupamiento por lanzador dentro del juego.** Los lanzamientos de un mismo
lanzador en un juego tienen residuos correlacionados (mando/liberación del lanzador, no capturados
por $f_D$). El SE **ingenuo** $\hat\sigma_\eta/\sqrt{n_g}$ supone independencia y subestima. Se usa el
estimador **robusto por conglomerados**, con conglomerados = (lanzador × juego):

$$\widehat{\operatorname{Var}}(\hat\delta_g)=\frac{1}{n_g^2}\sum_{p\in P(g)}\Big(\sum_{i\in p,\,g}\hat\eta_i\Big)^2,\qquad P(g)=\text{lanzadores del juego }g,$$

equivalente a $\dfrac{\sigma_\eta^2}{n_g}\big(1+(\bar m_g-1)\,\text{ICC}_p\big)$ con $\bar m_g$ el
promedio de lanzamientos por lanzador en $g$ e $\text{ICC}_p$ la correlación intra-lanzador de
$\eta$. **G2.4** exige que la **mediana** de $\sqrt{\widehat{\operatorname{Var}}(\hat\delta_g)}$ sobre
los juegos sea $<0.03$. Se reportan el SE ingenuo y el agrupado para ver el efecto de diseño.

*Precisión esperada (§4-F2):* con ~250 lanzamientos/juego y $\sigma_\eta\approx0.15$, el SE ingenuo
$\approx0.01$; el agrupado será algo mayor según $\text{ICC}_p$, y debe seguir bajo 0.03 contra una
señal de 0.27.

## F2.4 Proposición 3 — robustez a sesgos de calibración (con el término de gravedad explícito)

**(a) Error de escala espacial $\lambda_g$ por parque** ($\tilde{\mathbf r}=\lambda\mathbf r$). Entonces
$\tilde{\mathbf v}=\lambda\mathbf v$, $\tilde{\mathbf a}=\lambda\mathbf a$ y, en la Prop. 1,
$\rho C_D$ se recupera como
$-\dfrac{2m}{A}\dfrac{\lambda\tilde{\mathbf a}\cdot\hat{\mathbf v}}{\lambda^2\lVert\bar{\mathbf v}\rVert^2}=\dfrac1\lambda(\rho C_D)_{\text{verdadero}}$:
$\hat\delta_g$ absorbe $-\log\lambda_g$. Un sesgo de 2 % da 0.02 de error en $\delta$, **un orden bajo
la señal** ($|\log0.762|=0.27$). Como $\lambda$ escala $C_D$ y $C_L$ **por igual**, $\delta^D$ y
$\delta^L$ se desplazan lo mismo: la **sobreidentificación (Deming) no se entera** y el orden/bandas
de G2.2 se conservan.

**(b) Error de reloj $\tau$** (el tiempo medido es $\tau$ veces el real). La posición es correcta pero
las derivadas no: $\tilde{\mathbf v}=\mathbf v/\tau$ y, para la aceleración **medida completa** (que
incluye gravedad), $\tilde{\mathbf a}_{\text{full}}=\mathbf a_{\text{full}}/\tau^2$. Al restar la
**gravedad verdadera**,

$$\tilde{\mathbf a}=\tilde{\mathbf a}_{\text{full}}-\mathbf g=\frac{\mathbf a_{\text{aero}}+\mathbf g}{\tau^2}-\mathbf g=\frac{\mathbf a_{\text{aero}}}{\tau^2}+\mathbf g(\tau^{-2}-1).$$

El cociente de la Prop. 1 queda, con $\lVert\tilde{\mathbf v}\rVert^2=\lVert\mathbf v\rVert^2/\tau^2$,

$$\frac{\tilde{\mathbf a}\cdot\hat{\mathbf v}}{\lVert\tilde{\mathbf v}\rVert^2}=\frac{\mathbf a_{\text{aero}}\cdot\hat{\mathbf v}}{\lVert\mathbf v\rVert^2}+(1-\tau^2)\,\frac{\mathbf g\cdot\hat{\mathbf v}}{\lVert\mathbf v\rVert^2},$$

es decir el valor verdadero **más** un término $\propto(1-\tau^2)\,\mathbf g\cdot\hat{\mathbf v}$. Como
el lanzamiento es casi horizontal, $\mathbf g\cdot\hat{\mathbf v}$ es pequeño: el **canal de arrastre
(a lo largo de $\hat{\mathbf v}$) casi no se afecta**. El residuo perpendicular (Magnus) recoge toda
la componente **vertical** de $\mathbf g(\tau^{-2}-1)$, así que el **canal de sustentación sí se
sesga**. Resultado: $\delta^D$ y $\delta^L$ **divergen**, con la discrepancia concentrada en la
vertical.

*Consecuencia (Prop. 3).* Un sesgo de sensor no fabrica el efecto altitud: la escala lo absorbe
(orden de magnitud bajo la señal) y el reloj deja huella detectable. **La prueba de
sobreidentificación $\delta^D$ vs $\delta^L$ (Deming, G2.3) es el detector.** $\blacksquare$

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
Recuperar $\rho C_D,\rho C_L$ con la Prop. 1 evaluada en $t_m$ y estimar $\delta_g$ con el estimador
de la Prop. 2. La sintética **corre aquí** (sin datos reales).

**Escenarios y qué compuerta responde a cada sesgo** (lo que pide el orquestador):

| escenario | qué se inyecta | efecto esperado | compuerta que responde |
|---|---|---|---|
| base + ruido | $\sigma_{\text{pos}}$ realista | recuperación de $\rho$ con error $<1\%$; fija $\sigma_\eta$ y el SE de $\delta_g$ | **G2.1** (error $<1\%$) y **G2.4** ($\sigma_\eta$, SE mediano $<0.03$) |
| escala $\lambda=1.02$ por parque | $\tilde{\mathbf r}=\lambda\mathbf r$ | $\hat\delta_g$ se corre $-\log1.02=-0.0198$ (2 %); orden/bandas G2.2 intactos; Deming sigue en pendiente 1 | **ninguna lo marca** (Prop. 3a): demuestra que la escala se absorbe y no puede fabricar la señal de 27 % |
| reloj $\tau=1.01$ | $\tilde{\mathbf v}=\mathbf v/\tau$, $\tilde{\mathbf a}_{\text{full}}=\mathbf a_{\text{full}}/\tau^2$ | $\delta^D$ y $\delta^L$ divergen; discrepancia concentrada en la vertical | **G2.3** (Deming: pendiente fuera de $[0.85,1.15]$) |

La sintética debe reportar, por escenario: error de recuperación de $\rho$ por nivel,
$\hat\sigma_\eta$, el SE ingenuo y el agrupado de $\hat\delta_g$, la pendiente/intercepto de Deming y
la fracción de la discrepancia $\delta^D-\delta^L$ que vive en la componente vertical. Así se ve que
G2.1/G2.4 miden precisión, G2.3 detecta el reloj, y la escala queda —por diseño— absorbida.

También cuantifica numéricamente $\varepsilon_{\text{mid}}$ (F2.2): comparar $\rho C$ recuperado con y
sin la corrección del punto medio confirma la cota $s^2/4$ y que $f_D$ absorbe el resto.

## F2.6 Prueba de Deming $\delta^D$ vs $\delta^L$ (c)

Bajo el modelo, $\delta^D_g=\delta^L_g$ (sobreidentificación). Ambos son ruidosos
(errores-en-variables), así que se usa **regresión de Deming** con razón de varianzas
$\lambda_{\text{Dem}}=\operatorname{Var}(\text{err }\delta^L)/\operatorname{Var}(\text{err }\delta^D)$
estimada de los SE por juego (F2.3). La hipótesis física es **pendiente 1, intercepto 0**. **G2.3**
aprueba si la pendiente $\in[0.85,1.15]$. Una desviación de la pendiente, con la discrepancia cargada
en la vertical, es la firma de un error de reloj (Prop. 3b): va al orquestador.

## F2.7 Mapa a las compuertas de F2

| compuerta | criterio (§4-F2) | de dónde sale |
|---|---|---|
| **G2.1** | error sintético de recuperación de $\rho<1\%$ | F2.5 base; cota teórica $\varepsilon_{\text{mid}}\le s^2/4$ (F2.2) |
| **G2.2** | orden $\bar\delta_{\text{No}}>\bar\delta_{\text{Medium}}>\bar\delta_{\text{Extreme}}$; $\bar\delta_{\text{Extreme}}\in[-0.30,-0.15]$; componente densa de *Extreme* en $[-0.32,-0.20]$ | F2.3 (medias por cubeta, parques latentes GMM+BIC 🔎) |
| **G2.3** | Deming $\delta^L$ sobre $\delta^D$: pendiente $\in[0.85,1.15]$ | F2.6 |
| **G2.4** | $\sigma_\eta$ medida y SE mediano de $\hat\delta_g<0.03$ | F2.3 (SE agrupado por lanzador) |

**Si G2.2 falla con G2.3 aprobada:** las cubetas no corresponden a la altitud supuesta. **Si G2.3
falla:** sesgo de sensor (Prop. 3b). Ambos van al orquestador.

**Ningún outcome entra en F2:** solo física por lanzamiento ($\mathbf r_0,\mathbf v_0,\mathbf a$,
`SpinRate`, `SpinAxis`, forma, mano, año). Los `*_anon_id` solo agrupan (SE por lanzador) y validan.
