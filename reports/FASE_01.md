# FASE 01 — Pre-registro de hipótesis

**Sin corrida local** (ROADMAP §4-F1). F1 no lee datos ni ejecuta análisis: fija H1–H6 antes de
que cualquier fase con outcomes corra. La **evidencia del pre-registro es el timestamp del commit
de merge a `main`** de esta fase.

## Qué se entregó

1. `docs/HIPOTESIS.md` — H1–H6 con el estadístico y la regla 🟢 **tal cual** de ROADMAP §4-F1, más,
   para cada una: variables exactas (columnas del diccionario y de F0: `familia`, `pitch_call_h`,
   `evento_terminal`, `es_*`), unidad de análisis, filtros (`excluir_modelo` / `excluir_cadena`),
   agrupamiento de errores (juego o lanzador) con su justificación, tamaño de efecto mínimo
   relevante, qué la refuta, y la lista exacta de pruebas que entran al único Benjamini–Hochberg
   (q = 0.10).
2. Sección **"Datos faltantes (ADR-016)"**: mecanismo U, `perdida_ignorable = false`; H3 y la
   corroboración de F8 se reportan además con intervalo de Imbens–Manski (Prop. 17); 🟢 exige BH
   **y** que el IM excluya el nulo, 🟡 si pasa BH pero el IM no lo excluye.
3. Sección **"Lo visto antes del pre-registro"**: cifras por cubeta de `reports/FASE_00.md`
   (alcance, $f_b$, tasa de P, OR del logit) y la declaración de que ninguna es estadístico de
   H1–H6.
4. `docs/DECISIONES.md`: se agregó al inicio la **plantilla de ADR** y el **ADR-001** (ρ por juego
   desde la trayectoria, porque el dataset no trae estadio ni clima). No se tocaron los ADR-002 a
   016.

## Lista del único Benjamini–Hochberg (q = 0.10, m = 5)

H1, H2, H3, H4, H6 — cada una aporta un valor-p de una cola. **H5 no entra** (es una prueba de no
rechazo / equivalencia; un p pequeño sería un fracaso, no un descubrimiento): se evalúa con no
rechazo a α = 0.10 y pendiente de calibración ∈ [0.95, 1.05]. Detalle y justificación en
`docs/HIPOTESIS.md`.

## Coherencia (ROADMAP §4-F1 punto 6)

Sin contradicción con ROADMAP ni con `reports/FASE_00.md`:

- H2 usa las familias de ADR-002 (CH = Changeup + Splitter; SL∪CU = Slider + Sweeper + Curveball): consistente.
- El mecanismo de datos faltantes es **U** (§1.5), que no quita lanzamientos: H1, H2, H4, H5, H6 no
  sufren sesgo de selección; solo H3 (contraste de outcomes entre cubetas) lleva el intervalo de
  Imbens–Manski, tal como pide el punto 2.
- `docs/HIPOTESIS.md` era un marcador ("lo escribe F1"): escribirlo aquí es el camino previsto, no
  una modificación indebida.

No se escribió `docs/discrepancias/D01_F1.md`.

### Bloque para el orquestador — F01
- Modelo(s) usado(s): Opus
- Compuertas: F1 no tiene compuertas (pre-registro, sin corrida local)
- Cifras clave: 0 análisis ejecutados · H1–H6 pre-registradas · BH único con m = 5 pruebas
  (H1, H2, H3, H4, H6); H5 por no rechazo + calibración ∈ [0.95, 1.05] · H3 (y corroboración de F8)
  con intervalo de Imbens–Manski (Prop. 17), 🟢 exige BH + IM excluye el nulo, si no 🟡
- Desviaciones respecto al ROADMAP: ninguna. Se operacionaliza el BH declarando que H5 (equivalencia)
  no entra al procedimiento de descubrimientos; no se cambió ningún estadístico ni regla 🟢 de §4-F1
- Mejora posible detectada: ninguna
- Riesgo de empeorar: ninguno
- Rama / PR / commit de resultados locales: fase01 / #3 / commit de pre-registro
  5ef4a87 · commit de merge (sello): b6a008c
- Log: no aplica (sin corrida local)
