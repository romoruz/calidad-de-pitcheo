"""Generador sintético. La pieza que permite trabajar sin los datos reales.

Produce un DataFrame con TODAS las columnas de `docs/diccionario.csv` y, desde F0, reproduce
también lo que `reports/FASE_00_0.md` encontró en los datos reales y el diccionario no dice:

  - los 12 AutoPitchType (TwoSeamFastBall, OneSeamFastBall, Sweeper, Knuckleball);
  - mano `Undefined` (y nula) en lanzador y bateador, bateadores `Switch`;
  - `FoulBall` dividido en tres + `PitchCall = Undefined`;
  - cubeta de altitud nula, en juegos completos y en filas sueltas;
  - `Outs = 3`; los 16 `play_result` (incluidos los que son valores de lanzamiento);
  - nulos en IDs, SpinAxis/Tilt/breaks, Extension, SpinRate, Distance;
  - el esquema de tipos REAL: flags y enteros como Float64, `EffectiveVelo` como texto,
    `Tilt` sin cero a la izquierda ("1:00"), `is_hit_by_pitch` siempre 0, categóricas de polars.

Los valores cumplen las identidades de ROADMAP §4-F0 por construcción:

  I1  SpeedDrop = RelSpeed - ZoneSpeed                 (exacto)
  I2  count = f(Balls, Strikes)                        (exacto)
  I3  2 * PitchTrajectory?c2 = a?0                     (exacto: c2 = a0/2)
  I4  VertBreak - InducedVertBreak = -1/2 g ZoneTime^2 (exacto, en pulgadas)
  I5  Tilt <-> SpinAxis biyectivos                     (mapa reloj)
  I6′ is_swing = is_whiff + is_contact; is_contact <=> pitch_call_h en {Foul, InPlay}
  I7  suma de OutsOnPlay por media entrada = 3         (se simula hasta 3 outs)
  I8  signo de HorzBreak se invierte con PitcherThrows para el mismo tipo
  I9  altitude_category constante dentro de cada juego (los nulos son aparte)
  I10 Outs en {0,1,2} salvo las filas sembradas con Outs = 3

NO son los datos reales. La física es la mínima para que las identidades valgan y las
magnitudes sean plausibles; F2 extiende este módulo con física exacta y rho conocida.
`generar(..., sucio=False)` devuelve el dato limpio de defectos (sin los casos de D00).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from .fisica import A_BOLA, FT_M, G_SI, M_BOLA, R_BOLA, RPM_RADS, Y_FRENTE_PLATO_FT
from .io import ColSpec, leer_diccionario

FTPS_A_MPH = 3600.0 / 5280.0
G_FTS2 = 32.174
Y_FRENTE_PLATO = 17.0 / 12.0  # ft
Y_NUEVE_P = 50.0              # el reloj de los 9P arranca en y0 = 50 ft (ADR-014); ZoneTime y los polinomios, en la liberación
# Verdad sembrada del generador (ADR-014): PlateLocSide = SIGNO * x(t_p). Es una hipótesis del orquestador (ROADMAP §1.3:
# "apunta a un signo invertido"); el código NO la supone: la elige por mínimo error y las pruebas verifican que la recupere.
SIGNO_PLATELOC_X = -1

# Cubetas REALES (ROADMAP §1.1, ADR-005). Extreme mezcla varios parques sobre ~1 800 m.
CUBETAS_DEFECTO = {
    "No Altitude":      {"altitudes_m": [3, 10, 40],        "peso_juegos": 0.46},
    "Medium Altitude":  {"altitudes_m": [532, 600],         "peso_juegos": 0.25},
    "Extreme Altitude": {"altitudes_m": [1921, 2192, 2232], "peso_juegos": 0.29},
}

# Escenario de G2.3b (ROADMAP F2.5b): 6 parques por cubeta → λ en 2, τ en 2 y 2 limpios por cubeta.
CUBETAS_G23B = {
    "No Altitude":      {"altitudes_m": [3, 10, 40, 60, 85, 120],              "peso_juegos": 0.46},
    "Medium Altitude":  {"altitudes_m": [430, 532, 600, 680, 760, 820],        "peso_juegos": 0.25},
    "Extreme Altitude": {"altitudes_m": [1921, 2050, 2192, 2232, 2300, 2400],  "peso_juegos": 0.29},
}

# Parámetros base por tipo de lanzamiento, en el marco de un DIESTRO.
# magnus_z, magnus_x en ft/s^2 (break ~ 0.5 * magnus * ZoneTime^2 * 12 pulgadas).
# magnus_x>0 = lado del brazo del diestro; para zurdos se invierte (I8).
_TIPOS = {
    "Four-Seam":       {"vel": 94, "spin": 2300, "axis": 205, "mz": 15.0, "mx": 7.0,   "peso": 0.330},
    "Sinker":          {"vel": 92, "spin": 2150, "axis": 230, "mz": 9.0,  "mx": 14.0,  "peso": 0.080},
    "TwoSeamFastBall": {"vel": 93, "spin": 2200, "axis": 225, "mz": 10.0, "mx": 13.0,  "peso": 0.060},
    "OneSeamFastBall": {"vel": 93, "spin": 2100, "axis": 235, "mz": 9.0,  "mx": 12.0,  "peso": 0.010},
    "Cutter":          {"vel": 89, "spin": 2400, "axis": 160, "mz": 8.0,  "mx": -3.0,  "peso": 0.060},
    "Changeup":        {"vel": 85, "spin": 1750, "axis": 240, "mz": 8.0,  "mx": 13.0,  "peso": 0.090},
    "Splitter":        {"vel": 86, "spin": 1500, "axis": 225, "mz": 4.0,  "mx": 8.0,   "peso": 0.030},
    "Slider":          {"vel": 85, "spin": 2500, "axis": 120, "mz": 1.0,  "mx": -11.0, "peso": 0.140},
    "Sweeper":         {"vel": 82, "spin": 2600, "axis": 100, "mz": 0.0,  "mx": -17.0, "peso": 0.030},
    "Curveball":       {"vel": 79, "spin": 2650, "axis": 40,  "mz": -12.0, "mx": -9.0, "peso": 0.090},
    "Knuckleball":     {"vel": 76, "spin": 300,  "axis": 180, "mz": 2.0,  "mx": 1.0,   "peso": 0.002},
    "Other":           {"vel": 85, "spin": 2000, "axis": 180, "mz": 6.0,  "mx": 2.0,   "peso": 0.005},
}

# Vocabulario REAL de hit_type (sin espacios) y su mezcla aproximada.
_HIT_TYPES = ["GroundBall", "LineDrive", "FlyBall", "Popup", "Bunt"]
_P_HIT_TYPES = [0.42, 0.24, 0.22, 0.08, 0.04]

# ADR-012: el ~13 % de las medias entradas reales termina con 2 outs (y ~0.75 % con 0-1). Se reproduce con un
# tercer out SIN lanzamiento propio (robo, pickoff): la media entrada se corta en mitad de un turno.
_P_CORTE = {2: 0.015, 1: 0.004, 0: 0.004}

# ADR-016 (ROADMAP §1.4): las medias entradas con 2 outs registrados son, sobre todo, outs que `OutsOnPlay` no cuenta
# (U): dobles matanzas registradas como 1 out y outs de corredor entre lanzamientos. El simulador base-out las
# reproduce; la pérdida real de turnos (L) es opcional y arranca en cero.
P_DOBLE_MATANZA = 0.47          # P(doble matanza | rodado de out, corredor en 1B, < 2 outs): ≈ 1.6-2.0 por juego
P_DP_CONTADA_COMO_1 = 0.93      # `OutsOnPlay` = 1 en el 93 % de las dobles matanzas (reportes de F0: casi no hay 2)
P_EXTRA = 0.06                  # fracción de juegos que pasan a extra innings (corredor fantasma en 2B desde la 10.ª)
P_PICKOFF_FANTASMA = 0.30       # el corredor colocado es puesto out entre lanzamientos (out real sin lanzamiento)
# Tráfico de corredores mayor en altura: P(un out en juego pasa a sencillo), por cubeta.
TRAFICO_DEFECTO = {"No Altitude": 0.0, "Medium Altitude": 0.15, "Extreme Altitude": 0.50}

# Resultados de bola en juego y su mezcla aproximada (nunca el 100 % de los datos reales).
_P_FOUL = {"FoulBall": 0.70, "FoulBallFieldable": 0.10, "FoulBallNotFieldable": 0.20}


def spinaxis_a_tilt(axis_deg: float) -> str:
    """Mapa reloj biyectivo (I5), sin cero a la izquierda como en el dato real ("1:00")."""
    total_min = round((float(axis_deg) % 360.0) / 360.0 * 720.0) % 720
    h = (total_min // 60) % 12
    m = total_min % 60
    h = 12 if h == 0 else h
    return f"{h}:{m:02d}"


def _densidad_rel(altitud_m: float) -> float:
    """rho/rho0 barométrica (ROADMAP §2)."""
    return (1.0 - 2.25577e-5 * altitud_m) ** 5.25588


def _fisica_lanzamiento(rng, tipo: str, mano: str, dens_scale: float, y_plano: float = Y_FRENTE_PLATO,
                        signo_x: int = SIGNO_PLATELOC_X) -> dict:
    """Un lanzamiento coherente: release, aceleración constante y derivadas.

    Devuelve todas las columnas de trayectoria, velocidad, movimiento y ángulos que cumplen I1 e I4 por
    construcción, y I8 vía el signo de mano. I3 (2·c2 = a0 en el mismo eje) FALLA a propósito, como en el dato
    real: los polinomios están permutados respecto de los 9P (ADR-010 enmendado).
    """
    p = _TIPOS[tipo]
    s = 1.0 if mano == "Right" else -1.0  # espejo del eje x para zurdos (I8)

    rel_speed_mph = max(55.0, rng.normal(p["vel"], 1.6))
    speed0 = rel_speed_mph / FTPS_A_MPH  # ft/s

    extension = float(np.clip(rng.normal(6.2, 0.35), 5.0, 7.5))
    rel_height = float(np.clip(rng.normal(5.8, 0.35), 4.0, 7.0))
    rel_side = s * float(np.clip(rng.normal(1.7, 0.4), 0.3, 3.2)) * -1.0  # diestro: lado 3B

    y0 = 60.5 - extension
    z0 = rel_height
    x0 = rel_side

    vra = rng.normal(-2.0, 1.2)      # ángulo vertical de salida (grados)
    hra = s * rng.normal(1.0, 1.2)   # ángulo horizontal de salida (grados)
    vz0 = speed0 * np.sin(np.radians(vra))
    vx0 = speed0 * np.sin(np.radians(hra))
    vy0 = -np.sqrt(max(speed0**2 - vx0**2 - vz0**2, 1.0))  # hacia el plato (-y)

    # Aceleraciones constantes (modelo 9P): arrastre + Magnus + gravedad.
    ay0 = float(rng.normal(29.0, 3.0)) * dens_scale          # arrastre (decelera -y)
    magnus_z = (p["mz"] + rng.normal(0, 1.5)) * dens_scale
    magnus_x = s * (p["mx"] + rng.normal(0, 1.5)) * dens_scale
    az0 = -G_FTS2 + magnus_z
    ax0 = magnus_x

    # Tiempo a cruzar el frente del plato: 0.5*ay0*t^2 + vy0*t + (y0 - yf) = 0.
    a_, b_, c_ = 0.5 * ay0, vy0, (y0 - y_plano)
    disc = max(b_**2 - 4 * a_ * c_, 0.0)
    t1 = (-b_ - np.sqrt(disc)) / (2 * a_)
    t2 = (-b_ + np.sqrt(disc)) / (2 * a_)
    tf = min([t for t in (t1, t2) if t > 0], default=0.45)

    # Velocidad y rapidez en el plato -> I1.
    vxf, vyf, vzf = vx0 + ax0 * tf, vy0 + ay0 * tf, vz0 + az0 * tf
    zone_speed_mph = np.sqrt(vxf**2 + vyf**2 + vzf**2) * FTPS_A_MPH
    speed_drop = rel_speed_mph - zone_speed_mph

    # Break respecto a la recta sin fuerzas: desviación = 0.5*a*tf^2 (-> pulgadas).
    f_in = 0.5 * tf**2 * 12.0
    horz_break = ax0 * f_in
    vert_break = az0 * f_in                 # incluye gravedad
    induced_vb = (az0 + G_FTS2) * f_in       # solo Magnus -> I4: VB - IVB = -1/2 g tf^2 *12

    # Ubicación en el plato (PlateLocSide con el signo sembrado; ADR-014).
    plate_side = signo_x * (x0 + vx0 * tf + 0.5 * ax0 * tf**2)
    plate_height = z0 + vz0 * tf + 0.5 * az0 * tf**2

    # Marco de los 9P (ADR-014): su reloj arranca en y = 50 ft, DESPUÉS de la liberación. t_s < 0 es el
    # instante de la liberación en ese reloj; ZoneTime (tf) y los polinomios cuentan desde la liberación.
    disc50 = max(vy0**2 - 4 * (0.5 * ay0) * (y0 - Y_NUEVE_P), 0.0)
    t50 = min(t for t in ((-vy0 - np.sqrt(disc50)) / ay0, (-vy0 + np.sqrt(disc50)) / ay0) if t > 0)
    r50 = (x0 + vx0 * t50 + 0.5 * ax0 * t50**2, Y_NUEVE_P, z0 + vz0 * t50 + 0.5 * az0 * t50**2)
    v50 = (vx0 + ax0 * t50, vy0 + ay0 * t50, vz0 + az0 * t50)

    # Ángulos de aproximación.
    vaa = np.degrees(np.arctan2(vzf, -vyf))
    haa = np.degrees(np.arctan2(vxf, -vyf))

    # pfx: movimiento sobre los últimos ~40 ft (proxy a partir del Magnus).
    esc = (40.0 / max(y0 - y_plano, 1.0)) ** 2
    pfxx = horz_break * esc
    pfxz = induced_vb * esc

    axis = (p["axis"] + rng.normal(0, 6)) % 360.0
    if mano == "Left":
        axis = (360.0 - axis) % 360.0

    eff_velo = rel_speed_mph + (extension - 6.2) * 1.5 + rng.normal(0, 0.8)

    return {
        "RelSpeed": rel_speed_mph, "EffectiveVelo": eff_velo, "ZoneSpeed": zone_speed_mph,
        "SpinRate": max(100.0, rng.normal(p["spin"], 120)), "SpinAxis": axis,
        "Tilt": spinaxis_a_tilt(axis),
        "RelHeight": rel_height, "RelSide": rel_side, "Extension": extension,
        "VertBreak": vert_break, "InducedVertBreak": induced_vb, "HorzBreak": horz_break,
        "VertRelAngle": vra, "HorzRelAngle": hra, "VertApprAngle": vaa, "HorzApprAngle": haa,
        "SpeedDrop": speed_drop, "ZoneTime": tf,
        "x0": r50[0], "y0": r50[1], "z0": r50[2], "vx0": v50[0], "vy0": v50[1], "vz0": v50[2],
        "ax0": ax0, "ay0": ay0, "az0": az0, "pfxx": pfxx, "pfxz": pfxz,
        # Polinomio de trayectoria (convención REAL, ADR-010 enmendado): son los 9P en ejes permutados
        # X->y, Y->z, Z->x (signos +) con el origen de tiempo en la liberación: c2 = a/2, c1 = v(liberación),
        # c0 = r(liberación). Con el reloj de los 9P: c1 = v0 + a·t_s y c0 = r0 + v0·t_s + ½·a·t_s², t_s = -t50.
        "PitchTrajectoryXc0": y0, "PitchTrajectoryXc1": vy0, "PitchTrajectoryXc2": ay0 / 2.0,
        "PitchTrajectoryYc0": z0, "PitchTrajectoryYc1": vz0, "PitchTrajectoryYc2": az0 / 2.0,
        "PitchTrajectoryZc0": x0, "PitchTrajectoryZc1": vx0, "PitchTrajectoryZc2": ax0 / 2.0,
        "PlateLocHeight": plate_height, "PlateLocSide": plate_side, "_t_s": -float(t50),
    }


def _desenlace(rng, en_zona: bool) -> dict:
    """PitchCall base ('FoulBall' sin dividir) y flags coherentes. No es terminal por sí mismo.

    Las probabilidades dan una mezcla de turnos parecida a la de una liga (ponches ≈ 21 %, bases por bolas ≈ 9 %, golpes
    ≈ 1 %, resto bola en juego) aunque la zona de strike del sintético sea chica; así el tráfico de corredores del
    simulador base-out (ADR-016) no depende de un exceso de bases por bolas.
    """
    p_swing = 0.70 if en_zona else 0.58
    swing = rng.random() < p_swing
    if swing:
        p_contacto = 0.85 if en_zona else 0.72
        if rng.random() < p_contacto:
            call = "InPlay" if rng.random() < 0.42 else "FoulBall"
        else:
            call = "StrikeSwinging"
    elif en_zona:
        call = "StrikeCalled"
    else:
        r = rng.random()
        call = "BallCalled" if r < 0.945 else ("BallinDirt" if r < 0.995 else "HitByPitch")
    return {"PitchCall": call}


def _flags_de_call(call: str) -> dict:
    """Flags de swing a partir del PitchCall base (I6′)."""
    is_swing = int(call in ("StrikeSwinging", "FoulBall", "InPlay"))
    is_whiff = int(call == "StrikeSwinging")
    is_contact = int(call in ("FoulBall", "InPlay"))
    return {"is_swing": is_swing, "is_whiff": is_whiff, "is_contact": is_contact,
            "is_called_strike": int(call == "StrikeCalled"), "is_swinging_strike": is_whiff,
            "is_ball_in_play": int(call == "InPlay")}


def _etiqueta_foul(rng, call: str) -> str:
    """El dato real divide FoulBall en tres etiquetas (ADR-004)."""
    if call != "FoulBall":
        return call
    return str(rng.choice(list(_P_FOUL), p=list(_P_FOUL.values())))


def _batazo(rng, dens_scale: float) -> dict:
    """Resultado de un batazo (InPlay). Carry mayor a menor densidad. `_outs` = outs de la jugada."""
    ht = str(rng.choice(_HIT_TYPES, p=_P_HIT_TYPES))
    exit_speed = float(np.clip(rng.normal(88, 12), 40, 118))
    angle = {"GroundBall": rng.normal(-5, 8), "LineDrive": rng.normal(14, 6),
             "FlyBall": rng.normal(32, 8), "Popup": rng.normal(60, 8), "Bunt": rng.normal(-12, 6)}[ht]
    direction = float(rng.normal(0, 22))
    base = max(0.0, exit_speed * 4.0 - abs(angle - 28) * 6.0)
    distance = float(np.clip(base * (1.0 + (1.0 - dens_scale) * 0.12) + rng.normal(0, 20), 0, 480))
    u = rng.random()
    if ht == "FlyBall" and distance > 380 and exit_speed > 98:
        res = "HomeRun"
    elif ht == "LineDrive" and exit_speed > 95 and u < 0.5:
        res = "Double" if rng.random() < 0.35 else ("Triple" if rng.random() < 0.12 else "Single")
    elif (ht == "GroundBall" and u < 0.26) or (ht == "LineDrive" and u < 0.55):
        res = "Single"
    else:
        r2 = rng.random()   # resto: out y sus variantes
        res = ("Error" if r2 < 0.02 else "FieldersChoice" if r2 < 0.09 else
               "Sacrifice" if r2 < 0.11 else "Out")
    return _resultado_bip(ht, exit_speed, angle, direction, distance, res)


def _resultado_bip(ht, ev, angle, direction, distance, res) -> dict:
    hit = res in ("Single", "Double", "Triple", "HomeRun")
    return {
        "hit_type": ht, "ExitSpeed": ev, "Angle": float(angle), "Direction": direction,
        "Distance": distance, "play_result": res, "is_hit": int(hit),
        "single": int(res == "Single"), "double": int(res == "Double"),
        "triple": int(res == "Triple"), "home_run": int(res == "HomeRun"),
        "_outs": int(res in ("Out", "FieldersChoice", "Sacrifice")),
    }


def _bases_por_bolas(bases):
    """Base por bolas o golpe: el bateador va a 1B y solo avanzan los corredores forzados."""
    b1, b2, b3 = bases
    return [True, b2 or b1, b3 or (b1 and b2)], int(b1 and b2 and b3)


def _bases_por_avance(bases, k):
    """El bateador llega a la base `k` (4 = jonrón) y cada corredor avanza `k` bases."""
    nuevas, carreras = [False] * 3, 0
    for pos in (i + 1 for i, ocupada in enumerate(bases) if ocupada):
        if pos + k >= 4:
            carreras += 1
        else:
            nuevas[pos + k - 1] = True
    if k >= 4:
        carreras += 1
    else:
        nuevas[k - 1] = True
    return nuevas, carreras


def _corredores_avanzan(bases):
    """Cada corredor avanza una base y el bateador no llega (sacrificio, rodado con corredor forzado)."""
    nuevas, carreras = [False] * 3, 0
    for pos in (i + 1 for i, ocupada in enumerate(bases) if ocupada):
        if pos == 3:
            carreras += 1
        else:
            nuevas[pos] = True
    return nuevas, carreras


def _jugada_bip(rng, bat, bases, outs, p_trafico, p_dp, p_dp_uno):
    """Bola en juego sobre el estado base-out: avance simple de corredores y outs REALES vs REGISTRADOS (ADR-016).

    Devuelve (bat, bases_nuevas, outs_reales, outs_registrados, carreras, es_doble_matanza). Con tráfico mayor
    un out de aire (no rodado) pasa a sencillo con probabilidad `p_trafico`. Un rodado de out con corredor en 1B y < 2 outs es doble
    matanza con probabilidad `p_dp`: 2 outs reales, y `OutsOnPlay` = 1 con probabilidad `p_dp_uno` (U: out no contado).
    """
    if bat["play_result"] == "Out" and bat["hit_type"] != "GroundBall" and rng.random() < p_trafico:
        bat = _resultado_bip(bat["hit_type"], bat["ExitSpeed"], bat["Angle"], bat["Direction"], bat["Distance"],
                             "Single")
    res = bat["play_result"]
    if res in ("Single", "Double", "Triple", "HomeRun", "Error"):
        nuevas, carreras = _bases_por_avance(bases, {"Double": 2, "Triple": 3, "HomeRun": 4}.get(res, 1))
        return bat, nuevas, 0, 0, carreras, False
    if res == "Sacrifice":
        nuevas, carreras = _corredores_avanzan(bases)
        return bat, nuevas, 1, 1, (carreras if outs + 1 < 3 else 0), False
    if res == "FieldersChoice" and bases[0]:          # el corredor de 1B es el out; el bateador queda en 1B
        nuevas, carreras = _corredores_avanzan([False, bases[1], bases[2]])
        nuevas[0] = True
        return bat, nuevas, 1, 1, (carreras if outs + 1 < 3 else 0), False
    if res == "Out" and bat["hit_type"] == "GroundBall" and bases[0] and outs < 2 and rng.random() < p_dp:
        registrados = 1 if rng.random() < p_dp_uno else 2
        return bat, [False, False, bases[1]], 2, registrados, int(bases[2] and outs + 2 < 3), True
    return bat, list(bases), 1, 1, 0, False


_COLS_BATAZO_NULAS = {
    "hit_type": None, "ExitSpeed": None, "Angle": None, "Direction": None, "Distance": None,
    "play_result": None, "is_hit": 0, "single": 0, "double": 0, "triple": 0, "home_run": 0,
    "_outs": 0,
}


def _play_result_no_bip(rng, call_etq: str, korbb: str) -> str:
    """play_result de un lanzamiento que no es bola en juego (mezcla lanzamiento/turno, ADR-007)."""
    if korbb == "Strikeout":
        return "Strikeout"
    if korbb == "Walk":
        return "Walk"
    if call_etq == "HitByPitch":
        return "HitByPitch"
    eco = {"BallCalled": ("BallCalled", 0.6), "BallinDirt": ("BallinDirt", 0.6),
           "StrikeSwinging": ("StrikeSwinging", 0.5), "FoulBallFieldable": ("FoulBallFieldable", 0.7)}
    if call_etq in eco and rng.random() < eco[call_etq][1]:
        return eco[call_etq][0]
    return "NeutralPlay"


def _conteo_antes(call, balls_despues, strikes_despues):
    """Balls y Strikes ANTES del lanzamiento, a partir del estado posterior."""
    b, s = balls_despues, strikes_despues
    if call in ("StrikeCalled", "StrikeSwinging"):
        s = strikes_despues - 1
    elif call == "FoulBall":
        s = strikes_despues if strikes_despues == 2 else strikes_despues - 1
    elif call in ("BallCalled", "BallinDirt", "BallIntentional"):
        b = balls_despues - 1
    return int(max(0, min(b, 3))), int(max(0, min(s, 2)))


def generar(n_juegos: int = 40, semilla: int = 2026, cubetas: dict | None = None,
            n_lanzadores: int = 60, n_bateadores: int = 120, n_receptores: int = 24,
            n_lanzadores_nucleo: int = 12, anios: tuple[int, ...] = (2024, 2025, 2026),
            innings_por_juego: int = 9, sucio: bool = True,
            convencion_polinomio: dict | str | None = None, con_verdad: bool = False,
            perdida_cubeta: dict | None = None, sesgo_k: float = 1.0, trafico_cubeta: dict | None = None,
            p_doble_matanza: float = P_DOBLE_MATANZA, p_dp_contada_como_1: float = P_DP_CONTADA_COMO_1,
            p_extra: float = P_EXTRA, p_pickoff_fantasma: float = P_PICKOFF_FANTASMA,
            signo_plateloc_x: int = SIGNO_PLATELOC_X,
            y_plano_ft: float = Y_FRENTE_PLATO) -> pl.DataFrame | tuple[pl.DataFrame, dict]:
    """Genera un dataset sintético con el esquema (y, si `sucio`, los defectos) de los datos reales.

    Cada lanzador tiene una mano fija y cada bateador un lado fijo (algunos son `Switch`), de
    modo que la imputación por moda de ADR-003 tiene sentido. El núcleo de lanzadores aparece
    en muchos juegos (identificación intra-lanzador).

    `convencion_polinomio`: `None` = la REAL (ADR-010 enmendado); un dict `{"X": ("z", -1), ...}` = permutación
    con signo SIN desfase de tiempo; `"ruido"` = polinomios sin relación con los 9P.

    **Simulador base-out (ADR-016, ROADMAP §1.4).** Cada media entrada lleva outs REALES y corredores en 1B/2B/3B con
    avance simple; la columna `Outs` es el estado previo real. `OutsOnPlay` es lo que registra el dato: 1 siempre en un
    ponche y 1 en el `p_dp_contada_como_1` de las dobles matanzas (U: out no contado). `trafico_cubeta` = P(un out en
    juego pasa a sencillo) por cubeta (más corredores en altura). Con probabilidad `p_extra` un juego sigue a extra
    innings, que arrancan con un corredor colocado en 2B; con `p_pickoff_fantasma` ese corredor es puesto out entre
    lanzamientos (out real sin turno y sin `OutsOnPlay`, con Z = 1: por eso F0 deja los extra innings fuera de T).
    `perdida_cubeta` = ℓ_b, la fracción de medias entradas completas (≤ 9) a las que se les pierde un turno de OUT
    (L: faltan todos sus lanzamientos); por defecto 0. Se asigna ESTRATIFICADA por cubeta y por Z (un acumulador por
    celda) para que la pérdida sea independiente de Z (S2 de la Prop. 16) sin el ruido de una moneda por entrada.
    `sesgo_k` > 1 hace más probable que el turno perdido sea un ponche.

    `signo_plateloc_x` y `y_plano_ft`: el signo y el plano con los que se escribe `PlateLocSide`/`ZoneTime`.
    `con_verdad=True` devuelve también la verdad sembrada (`t_s` por lanzamiento, plano, signo, turnos perdidos por
    tipo, dobles matanzas y cuántas se registraron como 1 out).
    """
    rng = np.random.default_rng(semilla)
    perdidos = {"K": 0, "OUT_BIP": 0, "SAC": 0}
    n_dp = n_dp_uno = 0
    fase_perdida: dict[tuple[str, int], float] = {}
    cubetas = cubetas or CUBETAS_DEFECTO
    nombres_cub = list(cubetas)
    pesos_cub = np.array([cubetas[c]["peso_juegos"] for c in nombres_cub], float)
    pesos_cub /= pesos_cub.sum()
    rho_ref = _densidad_rel(3.0)
    trafico = {**TRAFICO_DEFECTO, **(trafico_cubeta or {})}

    lanz = [f"pitcher_{i:05d}" for i in range(1, n_lanzadores + 1)]
    nucleo = lanz[:n_lanzadores_nucleo]
    bats = [f"batter_{i:05d}" for i in range(1, n_bateadores + 1)]
    recs = [f"catcher_{i:05d}" for i in range(1, n_receptores + 1)]
    mano_p = {p: str(rng.choice(["Right", "Left"], p=[0.72, 0.28])) for p in lanz}
    lado_b = {b: str(rng.choice(["Right", "Left"], p=[0.55, 0.45])) for b in bats}
    switch = {b: (i % 20 == 0) for i, b in enumerate(bats)}  # ~5 % de ambidiestros
    tipos = list(_TIPOS)
    pesos_tipo = np.array([_TIPOS[t]["peso"] for t in tipos], float)
    pesos_tipo /= pesos_tipo.sum()

    filas: list[dict] = []
    puid = 0
    for g in range(n_juegos):
        game_id = f"game_{g + 1:06d}"
        cub = nombres_cub[rng.choice(len(nombres_cub), p=pesos_cub)]
        alt_m = float(rng.choice(cubetas[cub]["altitudes_m"]))
        dens_scale = _densidad_rel(alt_m) / rho_ref
        anio = int(anios[rng.integers(0, len(anios))])
        tope = innings_por_juego + (1 + int(rng.random() < 0.3) if rng.random() < p_extra else 0)
        for inning in range(1, tope + 1):
            for mitad in ("Top", "Bottom"):
                lanzador = (nucleo[rng.integers(0, len(nucleo))] if rng.random() < 0.6
                            else lanz[rng.integers(0, len(lanz))])
                mano = mano_p[lanzador]
                receptor = recs[rng.integers(0, len(recs))]
                outs = 0                                   # outs REALES
                extra_innings = inning > innings_por_juego
                bases = [False, extra_innings, False]      # extra innings: corredor colocado en 2B
                if extra_innings and rng.random() < p_pickoff_fantasma:
                    outs, bases[1] = 1, False              # puesto out entre lanzamientos: out real, sin turno
                pa = 0
                media_cortada = False
                turnos: list[tuple[int, int, str]] = []    # (fila inicial, fila final, tipo) de cada turno completo
                while outs < 3 and not media_cortada:
                    pa += 1
                    fila_pa = len(filas)
                    corte = rng.random() < _P_CORTE.get(outs, 0.0)
                    n_corte, n_lanz = int(rng.integers(1, 4)), 0
                    forzar_out = pa > 20  # salvaguarda: media entrada siempre cierra
                    bateador = bats[rng.integers(0, len(bats))]
                    lado_etq = "Switch" if switch[bateador] else lado_b[bateador]
                    balls, strikes = 0, 0
                    terminada = False
                    outs_reales_jugada = 0
                    tipo_turno = "otro"
                    while not terminada:
                        puid += 1
                        tipo = tipos[rng.choice(len(tipos), p=pesos_tipo)]
                        fis = _fisica_lanzamiento(rng, tipo, mano, dens_scale, y_plano_ft, signo_plateloc_x)
                        en_zona = (1.5 <= fis["PlateLocHeight"] <= 3.5) and (abs(fis["PlateLocSide"]) <= 0.83)
                        call = "InPlay" if forzar_out else _desenlace(rng, en_zona)["PitchCall"]
                        flags = _flags_de_call(call)

                        # Transición del conteo y terminalidad.
                        korbb, outs_jugada, runs = "Undefined", 0, 0
                        extra = dict(_COLS_BATAZO_NULAS)
                        base_on_balls = strikeout = is_batted = 0
                        if call in ("StrikeCalled", "StrikeSwinging"):
                            strikes += 1
                            if strikes >= 3:
                                terminada, korbb, strikeout, outs_jugada = True, "Strikeout", 1, 1
                                outs_reales_jugada, tipo_turno = 1, "K"
                        elif call == "FoulBall":
                            strikes = min(strikes + 1, 2)
                        elif call in ("BallCalled", "BallinDirt", "BallIntentional"):
                            balls += 1
                            if balls >= 4:
                                terminada, korbb, base_on_balls = True, "Walk", 1
                                bases, runs = _bases_por_bolas(bases)
                                tipo_turno = "N"
                        elif call == "HitByPitch":
                            terminada = True
                            bases, runs = _bases_por_bolas(bases)
                            tipo_turno = "N"
                        elif call == "InPlay":
                            terminada, is_batted = True, 1
                            bat = _batazo(rng, dens_scale)
                            if forzar_out:
                                bat = _resultado_bip(bat["hit_type"], bat["ExitSpeed"], bat["Angle"],
                                                     bat["Direction"], bat["Distance"], "Out")
                            bat, bases, outs_reales_jugada, outs_jugada, runs, es_dp = _jugada_bip(
                                rng, bat, bases, outs, 0.0 if forzar_out else trafico.get(cub, 0.0),
                                p_doble_matanza, p_dp_contada_como_1)
                            n_dp += es_dp
                            n_dp_uno += es_dp and outs_jugada == 1
                            extra.update(bat)
                            res_bip = bat["play_result"]
                            tipo_turno = ("N" if res_bip in ("Single", "Double", "Triple", "Error")
                                          else "SAC" if res_bip == "Sacrifice"
                                          else "OUT_BIP" if outs_reales_jugada else "otro")

                        call_etq = _etiqueta_foul(rng, call)
                        play_result = (extra["play_result"] if call == "InPlay"
                                       else _play_result_no_bip(rng, call_etq, korbb))
                        b_antes, s_antes = _conteo_antes(call, balls, strikes)
                        filas.append({
                            "year": anio, "PitchUID": f"pitch_{puid:08d}", "game_anon_id": game_id,
                            "pitcher_anon_id": lanzador, "batter_anon_id": bateador,
                            "catcher_anon_id": receptor, "PitcherThrows": mano, "BatterSide": lado_etq,
                            "altitude_category": cub, "AutoPitchType": tipo,
                            **{k: fis[k] for k in (
                                "RelSpeed", "EffectiveVelo", "ZoneSpeed", "SpinRate", "SpinAxis", "Tilt",
                                "RelHeight", "RelSide", "Extension", "VertBreak", "InducedVertBreak",
                                "HorzBreak", "VertRelAngle", "HorzRelAngle", "VertApprAngle", "HorzApprAngle",
                                "SpeedDrop", "ZoneTime", "x0", "y0", "z0", "vx0", "vy0", "vz0",
                                "ax0", "ay0", "az0", "pfxx", "pfxz",
                                "PitchTrajectoryXc0", "PitchTrajectoryXc1", "PitchTrajectoryXc2",
                                "PitchTrajectoryYc0", "PitchTrajectoryYc1", "PitchTrajectoryYc2",
                                "PitchTrajectoryZc0", "PitchTrajectoryZc1", "PitchTrajectoryZc2")},
                            "PitchCall": call_etq, "KorBB": korbb,
                            "play_result": play_result, "hit_type": extra["hit_type"],
                            "ExitSpeed": extra["ExitSpeed"], "Angle": extra["Angle"],
                            "Direction": extra["Direction"], "Distance": extra["Distance"],
                            **flags, "is_batted": is_batted,
                            "is_hit": extra["is_hit"], "single": extra["single"], "double": extra["double"],
                            "triple": extra["triple"], "home_run": extra["home_run"],
                            "base_on_balls": base_on_balls, "strikeout": strikeout,
                            # En el dato real is_hit_by_pitch es SIEMPRE 0 (reports/FASE_00_0.md): el
                            # HBP solo se ve en PitchCall/play_result. Por eso ADR-007 usa pitch_call_h.
                            "is_hit_by_pitch": 0, "RunsScored": runs, "OutsOnPlay": outs_jugada,
                            "Inning": inning, "Top/Bottom": mitad, "Outs": outs,
                            "Balls": b_antes, "Strikes": s_antes, "count": f"{b_antes}-{s_antes}",
                            "PlateLocHeight": fis["PlateLocHeight"], "PlateLocSide": fis["PlateLocSide"],
                            "in_strike_zone": int(en_zona), "outside_strike_zone": int(not en_zona),
                            "swung_outside_strike_zone": int(flags["is_swing"] and not en_zona),
                            "_t_s": fis["_t_s"],
                        })
                        n_lanz += 1
                        if corte and not terminada and n_lanz >= n_corte:
                            media_cortada = True   # tercer out sin lanzamiento: el turno queda incompleto
                            break
                    if not media_cortada:
                        turnos.append((fila_pa, len(filas), tipo_turno))
                    outs += outs_reales_jugada
                # L: se pierden todos los lanzamientos de un turno de OUT de la media entrada (ADR-016, Prop. 16).
                ell = (perdida_cubeta or {}).get(cub, 0.0)
                con_out = [t for t in turnos if t[2] in perdidos]
                if ell > 0 and con_out and not media_cortada and not extra_innings:
                    z = int(all(t[2] != "N" for t in turnos))
                    acum = fase_perdida.setdefault((cub, z), float(rng.random())) + ell
                    if acum >= 1.0:
                        peso = np.array([sesgo_k if t[2] == "K" else 1.0 for t in con_out])
                        ini, fin, tipo_perdido = con_out[rng.choice(len(con_out), p=peso / peso.sum())]
                        del filas[ini:fin]
                        perdidos[tipo_perdido] += 1
                        acum -= 1.0
                    fase_perdida[(cub, z)] = acum
    df = _convencion_polinomio(pl.DataFrame(filas), convencion_polinomio, rng)
    if sucio:
        df = _ensuciar(df, rng, n_juegos)
    ts = df["_t_s"].to_numpy()
    out = _tipar_real(df, leer_diccionario(_RAIZ / "docs" / "diccionario.csv"))
    if not con_verdad:
        return out
    return out, {"t_s": ts, "y_plano_ft": y_plano_ft, "signo_x": signo_plateloc_x, "perdidos": perdidos,
                 "dobles_matanzas": n_dp, "dobles_matanzas_como_1_out": n_dp_uno}


# --------------------------------------------------------------------------
# ADR-010: ejes de los polinomios de trayectoria
# --------------------------------------------------------------------------
def _convencion_polinomio(df: pl.DataFrame, conv: dict | str | None, rng) -> pl.DataFrame:
    """Reescribe PitchTrajectory{X,Y,Z}c{0,1,2} según la convención pedida.

    - `None`: la convención REAL (ADR-010 enmendado): ya está escrita por `_fisica_lanzamiento` (ejes permutados
      X->y, Y->z, Z->x y origen en la liberación); no se toca.
    - dict `{"X": ("z", -1), "Y": ("y", -1), "Z": ("x", 1)}`: el eje P del polinomio es s·(eje q de los
      9P): c0=s·r0^q, c1=s·v0^q, c2=s·a0^q/2 (permutación con signo).
    - `"ruido"`: polinomios sin relación con los 9P (no canónicos).
    """
    if conv is None:
        return df
    n = df.height
    if conv == "ruido":
        exprs = []
        for p in "XYZ":
            for k in (0, 1, 2):
                c = f"PitchTrajectory{p}c{k}"
                sd = float(df[c].std() or 1.0)
                exprs.append(pl.Series(c, rng.normal(0.0, sd, n)))
        return df.with_columns(exprs)
    fuente = {"c0": {"x": "x0", "y": "y0", "z": "z0"}, "c1": {"x": "vx0", "y": "vy0", "z": "vz0"},
              "c2": {"x": "ax0", "y": "ay0", "z": "az0"}}
    exprs = []
    for p, (q, signo) in conv.items():
        for k, esc in (("c0", 1.0), ("c1", 1.0), ("c2", 0.5)):
            exprs.append((signo * esc * pl.col(fuente[k][q])).alias(f"PitchTrajectory{p}{k}"))
    return df.with_columns(exprs)


# --------------------------------------------------------------------------
# Defectos del dato real (reports/FASE_00_0.md, ROADMAP §1.1)
# --------------------------------------------------------------------------
def _mascara(rng, n: int, tasa: float, minimo: int = 0) -> pl.Series:
    """Máscara booleana con `tasa` de filas verdaderas (al menos `minimo`, pocas)."""
    k = min(n, max(minimo, round(n * tasa)))
    m = np.zeros(n, dtype=bool)
    m[rng.choice(n, size=k, replace=False)] = True
    return pl.Series(m)


def _nulificar(df: pl.DataFrame, mask: pl.Series, cols: list[str]) -> pl.DataFrame:
    return df.with_columns([pl.when(mask).then(None).otherwise(pl.col(c)).alias(c) for c in cols])


def _fijar(df: pl.DataFrame, mask: pl.Series, col: str, valor) -> pl.DataFrame:
    return df.with_columns(pl.when(mask).then(pl.lit(valor)).otherwise(pl.col(col)).alias(col))


def _id_por_cuantil(df: pl.DataFrame, col: str, q: float = 0.5, excluir: set[str] | None = None) -> str:
    """El id cuyo número de filas cae en el cuantil `q` (para sembrar un caso sobre un jugador real)."""
    c = df.filter(pl.col(col).is_not_null()).group_by(col).len().sort("len", col)  # desempate por id: determinista
    if excluir:
        c = c.filter(~pl.col(col).is_in(list(excluir)))
    return str(c[col][int(q * (c.height - 1))])


def _ensuciar(df: pl.DataFrame, rng, n_juegos: int) -> pl.DataFrame:
    """Siembra cada caso real de D00 con pocas filas, para que cada ADR tenga qué hacer."""
    n = df.height
    # Nulos físicos reales: SpinAxis/Tilt/breaks juntos (0.11 %), Extension, SpinRate.
    df = _nulificar(df, _mascara(rng, n, 0.0011, 4),
                    ["SpinAxis", "Tilt", "VertBreak", "InducedVertBreak", "HorzBreak"])
    df = _nulificar(df, _mascara(rng, n, 0.0012, 3), ["Extension"])
    df = _nulificar(df, _mascara(rng, n, 0.00013, 2), ["SpinRate"])
    df = _nulificar(df, _mascara(rng, n, 0.22, 0) & df["Distance"].is_not_null(), ["Distance"])

    # IDs nulos (0.5 % lanzador, 0.3 % bateador, 0.4 % receptor).
    m_p = _mascara(rng, n, 0.005, 4)
    df = _nulificar(df, m_p, ["pitcher_anon_id"])
    df = _nulificar(df, _mascara(rng, n, 0.003, 3), ["batter_anon_id"])
    df = _nulificar(df, _mascara(rng, n, 0.0037, 3), ["catcher_anon_id"])

    # ADR-003: mano Undefined / nula, un lanzador sin mano en NINGUNA fila (-> signo de RelSide),
    # un bateador sin lado en ninguna fila (-> descartado) y filas sin ninguna salida (-> descartadas).
    sin_mano = _id_por_cuantil(df, "pitcher_anon_id")
    df = _fijar(df, _mascara(rng, n, 0.0015, 3), "PitcherThrows", "Undefined")
    df = _nulificar(df, _mascara(rng, n, 0.0018, 3), ["PitcherThrows"])
    df = _fijar(df, pl.col("pitcher_anon_id") == sin_mano, "PitcherThrows", "Undefined")
    df = _fijar(df, _mascara(rng, n, 0.0015, 3), "BatterSide", "Undefined")
    df = _nulificar(df, _mascara(rng, n, 0.0015, 3), ["BatterSide"])
    ids_switch = {f"batter_{i + 1:05d}" for i in range(0, 5000, 20)}  # los ambidiestros de generar()
    sin_lado = _id_por_cuantil(df, "batter_anon_id", 0.15, excluir=ids_switch)
    df = _fijar(df, pl.col("batter_anon_id") == sin_lado, "BatterSide", "Undefined")
    sin_salida = m_p & _mascara(rng, n, 0.5, 3)
    df = _fijar(df, sin_salida, "PitcherThrows", "Undefined")
    df = _nulificar(df, sin_salida, ["RelSide"])

    # ADR-004: PitchCall = Undefined en lanzamientos no terminales (flags de swing en 0).
    no_term = ((pl.col("is_batted") == 0) & (pl.col("KorBB") == "Undefined")
               & (pl.col("PitchCall") != "HitByPitch"))
    cand = df.select(no_term).to_series()
    m_u = _mascara(rng, n, 0.001, 3) & cand
    if not m_u.any():
        m_u = pl.Series(np.isin(np.arange(n), np.flatnonzero(cand.to_numpy())[:3]))
    df = _fijar(df, m_u, "PitchCall", "Undefined")
    for c in ("is_swing", "is_whiff", "is_contact", "is_called_strike", "is_swinging_strike",
              "swung_outside_strike_zone"):
        df = _fijar(df, m_u, c, 0)

    # ADR-006: Outs = 3 (errores de captura).
    df = _fijar(df, _mascara(rng, n, 1.3e-5, 3), "Outs", 3)

    # ADR-005: cubeta nula, en juegos completos y en filas sueltas.
    juegos = df["game_anon_id"].unique().sort().to_list()
    nulos = list(rng.choice(juegos, size=min(len(juegos), max(1, round(0.02 * n_juegos))), replace=False))
    en_nulo = pl.col("game_anon_id").is_in(nulos)
    df = _nulificar(df, df.select(en_nulo).to_series(), ["altitude_category"])
    sueltas = _mascara(rng, n, 0.003, 5) & ~df.select(en_nulo).to_series()
    df = _nulificar(df, sueltas, ["altitude_category"])
    return _ensuciar_v24(df, rng)


def _ensuciar_v24(df: pl.DataFrame, rng) -> pl.DataFrame:
    """Casos de la corrida real de F0 (ROADMAP §1.2, ADR-011 a 013)."""
    n = df.height
    # ADR-012: medias entradas con >= 4 outs (inconsistentes): se suman dos outs a dos medias entradas.
    claves = df.select("game_anon_id", "Inning", "Top/Bottom").unique(maintain_order=True)
    for g, i, m in claves.sample(n=min(2, claves.height), seed=int(rng.integers(1_000_000))).iter_rows():
        en = ((pl.col("game_anon_id") == g) & (pl.col("Inning") == i) & (pl.col("Top/Bottom") == m)
              & (pl.col("OutsOnPlay") == 0))
        idx = np.flatnonzero(df.select(en).to_series().to_numpy())[:2]
        df = _fijar(df, pl.Series(np.isin(np.arange(n), idx)), "OutsOnPlay", 1)

    # ADR-011: fouls con KorBB = Strikeout (foul tip atrapado: ponche marcado como foul).
    k_idx = np.flatnonzero(df.select((pl.col("KorBB") == "Strikeout")
                                     & (pl.col("PitchCall") == "StrikeSwinging")).to_series().to_numpy())
    if len(k_idx):
        m_k = pl.Series(np.isin(np.arange(n), rng.choice(k_idx, size=min(3, len(k_idx)), replace=False)))
        df = _fijar(df, m_k, "PitchCall", "FoulBall")
        for c, v in (("is_whiff", 0), ("is_swinging_strike", 0), ("is_contact", 1)):
            df = _fijar(df, m_k, c, v)

    # ADR-011: las is_* del organizador no son partición exacta de PitchCall. En el dato real
    # (reports/FASE_00.md): contacto <=> Foul/InPlay falla en ~0.25 % de las filas, swing = whiff + contacto
    # en ~0.07 %, y whiff => StrikeSwinging nunca falla. Se rompe is_contact en fouls; en el 72 % de esas
    # filas también is_swing (la suma sigue valiendo) y en el resto no (la suma falla). is_whiff no se toca.
    foul_idx = np.flatnonzero(df.select(pl.col("PitchCall").is_in(list(_P_FOUL))).to_series().to_numpy())
    if len(foul_idx):
        k = min(len(foul_idx), max(4, round(n * 0.0025)))
        elegidos = rng.choice(foul_idx, size=k, replace=False)
        m_c = pl.Series(np.isin(np.arange(n), elegidos))
        m_conserva = pl.Series(np.isin(np.arange(n), elegidos[:max(1, round(0.28 * k))]))
        df = _fijar(df, m_c, "is_contact", 0)
        df = _fijar(df, m_c & ~m_conserva, "is_swing", 0)

    # ADR-013: bola en juego sin resultado (play_result = NeutralPlay con InPlay).
    inplay = np.flatnonzero(df.select((pl.col("PitchCall") == "InPlay")
                                      & (pl.col("play_result") == "Out")).to_series().to_numpy())
    if len(inplay):
        m_i = pl.Series(np.isin(np.arange(n), rng.choice(inplay, size=min(3, len(inplay)), replace=False)))
        df = _fijar(df, m_i, "play_result", "NeutralPlay")
    return df


# --------------------------------------------------------------------------
# Esquema de tipos REAL (reports/FASE_00_0.md): flags y enteros Float64, EffectiveVelo texto
# --------------------------------------------------------------------------
_RAIZ = Path(__file__).resolve().parents[2]
_INT32 = {"year", "in_strike_zone"}
_CATEGORICAS = {"AutoPitchType", "PitchCall", "play_result", "Top/Bottom"}


def _tipar_real(df: pl.DataFrame, specs: list[ColSpec]) -> pl.DataFrame:
    """Orden del diccionario y dtypes tal como llegan los datos reales."""
    exprs = []
    for s in specs:
        if s.nombre not in df.columns:
            raise ValueError(f"el generador no produjo la columna documentada: {s.nombre}")
        c = pl.col(s.nombre)
        if s.nombre in _INT32:
            exprs.append(c.cast(pl.Int32))
        elif s.nombre == "EffectiveVelo":
            exprs.append(c.round(2).cast(pl.Utf8))
        elif s.es_booleana or s.es_numerica:
            exprs.append(c.cast(pl.Float64))
        elif s.nombre in _CATEGORICAS:
            exprs.append(c.cast(pl.Utf8).cast(pl.Categorical))
        else:
            exprs.append(c.cast(pl.Utf8))
    return df.select(exprs)


# --------------------------------------------------------------------------
# Escritura de los tres formatos
# --------------------------------------------------------------------------
def escribir_tres_formatos(df: pl.DataFrame, ruta_base: str | Path) -> dict:
    """Escribe el mismo dataset en .parquet, .pkl y .rds.

    `ruta_base` sin extensión (p. ej. data/raw/stuff_model_df). Devuelve tamaños
    en disco. El .rds exige tipos simples: las categóricas van como texto.
    """
    base = Path(ruta_base)
    base.parent.mkdir(parents=True, exist_ok=True)
    p_parquet = base.with_suffix(".parquet")
    p_pkl = base.with_suffix(".pkl")
    p_rds = base.with_suffix(".rds")

    df.write_parquet(p_parquet)
    pdf = df.to_pandas()
    pdf.to_pickle(p_pkl)

    import pyreadr
    pdf_rds = pdf.copy()
    for c in pdf_rds.columns:
        if pdf_rds[c].dtype == object or str(pdf_rds[c].dtype) == "category":
            pdf_rds[c] = pdf_rds[c].astype("string")
    pyreadr.write_rds(str(p_rds), pdf_rds)

    return {
        "parquet": p_parquet.stat().st_size,
        "pkl": p_pkl.stat().st_size,
        "rds": p_rds.stat().st_size,
        "filas": df.height,
        "columnas": df.width,
    }


# ==========================================================================
# F2 — física exacta con ρ conocida (solve_ivp DOP853) y calibración sesgada (Prop. 3′)
# ==========================================================================
# forma -> (rapidez mph, spin rpm, eficiencia de giro, SpinAxis de un diestro (°), C_D base, ángulo vertical de salida (°))
_FORMAS_FISICA = {
    "FF": (94.0, 2300.0, 0.92, 205.0, 0.340, 0.2),
    "SI": (92.5, 2150.0, 0.85, 230.0, 0.350, -0.8),
    "FC": (89.0, 2400.0, 0.50, 160.0, 0.345, -0.3),
    "SL": (85.0, 2500.0, 0.35, 120.0, 0.360, -1.8),
    "CU": (79.0, 2650.0, 0.75, 40.0, 0.370, -3.8),
    "CH": (85.0, 1750.0, 0.85, 235.0, 0.355, -1.3),
}
NIVELES_RHO = {"No Altitude": 1.00, "Medium Altitude": 0.82, "Extreme Altitude": 0.76}   # × ρ0 (Prompt 1, §4-F2)
RHO_0 = 1.2                                     # kg/m³: el nivel absoluto no importa (solo cocientes)
SIGNO_MAGNUS_X = 1                              # n̂_M(θ) = (σ·sinθ, 0, −cosθ): convención de la sintética


def direccion_magnus(spin_axis_deg, v_hat, signo_x: int = SIGNO_MAGNUS_X) -> np.ndarray:
    """n̂ (n, 3): dirección de la sustentación implícita en `SpinAxis` y perpendicular a v̂.

    180° = efecto hacia atrás (sustentación hacia arriba, +z), 0° = efecto hacia adelante (−z), ±90° = lateral. Se
    proyecta fuera de v̂ y se normaliza. Es la dirección que usa la sintética y la que decodifica F2 para el
    detector ê (el signo lateral σ lo fija F2 con los datos).
    """
    th = np.radians(np.asarray(spin_axis_deg, dtype=float))
    n_m = np.column_stack([signo_x * np.sin(th), np.zeros_like(th), -np.cos(th)])
    n = n_m - np.einsum("ij,ij->i", n_m, v_hat)[:, None] * v_hat
    return n / np.linalg.norm(n, axis=1)[:, None]


def _integrar_bloque(r0, v0, omega_hat, omega_t, cd, rho, t_max: float, dt: float):
    """DOP853 (rtol 1e-10) para un bloque de lanzamientos a la vez. Devuelve (t, y) con y: (6, N, nt)."""
    from scipy.integrate import solve_ivp

    n = r0.shape[0]
    kappa = (rho * A_BOLA / (2.0 * M_BOLA))                       # (N,)
    g_vec = np.array([0.0, 0.0, -G_SI])[:, None]

    def rhs(_t, s):
        u = s.reshape(6, n)
        v = u[3:]
        sp = np.sqrt(np.sum(v * v, axis=0))
        cd_t = cd * (1.0 + 0.2 * (sp / 40.0 - 1.0))                # dependencia mínima de Reynolds
        s_giro = R_BOLA * omega_t / sp
        cl = s_giro / (2.32 * s_giro + 0.4)                        # C_L = 1/(2.32 + 0.4/S) (Nathan)
        cruz = np.cross(omega_hat, v.T).T                        # ω̂ × v: perpendicular a v
        n_hat = cruz / np.sqrt(np.sum(cruz * cruz, axis=0))
        acel = g_vec - kappa * cd_t * sp * v + kappa * cl * sp**2 * n_hat
        return np.concatenate([v, acel]).ravel()

    t_eval = np.arange(0.0, t_max + 1e-12, dt)
    sol = solve_ivp(rhs, (0.0, t_max), np.concatenate([r0.T, v0.T]).ravel(), method="DOP853", t_eval=t_eval,
                    rtol=1e-10, atol=1e-12)
    return sol.t, sol.y.reshape(6, n, -1)


def _raiz_pequena(c0, c1, c2) -> np.ndarray:
    """Menor raíz positiva de c0 + c1·t + c2·t² = 0 (NaN si no hay)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        disc = c1**2 - 4 * c2 * c0
        raiz = np.sqrt(np.where(disc >= 0, disc, np.nan))
        t1, t2 = (-c1 - raiz) / (2 * c2), (-c1 + raiz) / (2 * c2)
        pos = lambda x: np.where(x > 0, x, np.inf)
        t = np.minimum(pos(t1), pos(t2))
    return np.where(np.isfinite(t), t, np.nan)


def _ajustar_bloque(r0, v0, omega_hat, omega_t, cd, rho, lam, tau, rng, dt: float, paso: int, sigma_pos_m: float):
    """Integra un bloque, muestrea, añade ruido de posición y ajusta el 9P (polinomio de grado 2 por eje).

    Devuelve (coef (m, 3, 3), t_vuelo (m,)): coeficientes c0..c2 por eje en ft y s sobre el reloj MEDIDO (escala τ)
    y posiciones medidas (escala λ), y el tiempo de vuelo verdadero.
    """
    yp_m = Y_FRENTE_PLATO_FT * FT_M
    _t, ys = _integrar_bloque(r0, v0, omega_hat, omega_t, cd, rho, 0.65, dt)
    pos = np.moveaxis(ys[:3], 0, -1)                # (N, nt, 3) en m
    coef = np.empty((pos.shape[0], 3, 3))
    t_vuelo = np.empty(pos.shape[0])
    for q in range(pos.shape[0]):
        y_q = pos[q, :, 1]
        cruza = np.flatnonzero(y_q <= yp_m)
        fin = int(cruza[0]) if len(cruza) else len(y_q) - 1
        idx = np.arange(0, fin + 1, paso)
        t_meas = idx * dt * tau[q]
        medido = lam[q] * pos[q, idx, :] / FT_M + rng.normal(0, sigma_pos_m / FT_M, (len(idx), 3))
        coef[q] = np.polynomial.polynomial.polyfit(t_meas, medido, 2)
        t_vuelo[q] = fin * dt
    return coef, t_vuelo


def esquema_calibracion_parques(cubetas: dict | None, semilla: int, lambda_escala: float = 1.02,
                                tau_reloj: float = 1.01, fraccion: float = 1.0 / 3.0) -> dict:
    """ROADMAP F2.5b: en cada cubeta, λ en ≈1/3 de los parques, τ en otro ≈1/3 y el resto limpio.

    Devuelve {índice de parque: (λ, τ)} solo para los parques sesgados (el resto no aparece). Usa su propio flujo
    aleatorio (semilla, 17) para no alterar la física de `generar_fisica`.
    """
    cubetas = cubetas or CUBETAS_DEFECTO
    rg = np.random.default_rng([semilla, 17])
    out, base = {}, 0
    for spec in cubetas.values():
        m = len(spec["altitudes_m"])
        orden = rg.permutation(m)
        k = max(1, round(fraccion * m))
        for i in orden[:k]:
            out[base + int(i)] = (lambda_escala, 1.0)
        for i in orden[k:2 * k]:
            out[base + int(i)] = (1.0, tau_reloj)
        base += m
    return out


def generar_fisica(n_juegos: int = 45, lanzamientos_por_juego: int = 111, semilla: int = 2026,
                   niveles_rho: dict | None = None, cubetas: dict | None = None, sigma_pos_m: float = 0.015,
                   sigma_alpha: float = 0.05, sigma_cd_lanzamiento: float = 0.03, sigma_clima: float = 0.005,
                   sigma_parque: float = 0.0, n_staff: int = 8, p_local: float = 0.7, apariciones_por_juego: int = 9,
                   lambda_escala: float = 1.0, tau_reloj: float = 1.0, cubetas_sesgo=("Extreme Altitude",),
                   spinaxis_inferido: bool = False, anios=(2024, 2025, 2026), tasa_muestreo_hz: float = 100.0,
                   bloque: int = 400, calibracion_parques: dict | None = None,
                   n_jobs: int = 1) -> tuple[pl.DataFrame, dict]:
    """Sintética de F2 con física exacta: ρ conocida por juego, C_D y C_L realistas, ruido de posición y calibración sesgada.

    Cada lanzamiento se integra con `solve_ivp` (DOP853, rtol 1e-10):  r̈ = g − κ C_D ‖v‖ v + κ C_L ‖v‖² n̂, con
    κ = ρA/2m, n̂ = ω̂ × v / ‖ω̂ × v‖, C_L = 1/(2.32 + 0.4/S) y C_D = c_D(forma)·exp(α_j + ε_i). La densidad entra SOLO
    por κ (C_D y C_L son de la pelota y de la forma, no del parque). Luego se muestrea la trayectoria a
    `tasa_muestreo_hz` entre la liberación y el plato, se le añade ruido gaussiano de `sigma_pos_m` por eje, y
    **se reajusta un 9P de aceleración constante por mínimos cuadrados** (a, v0 y r0 en y0 = 50 ft, como Trackman;
    el polinomio X↔y arranca en la liberación, de modo que t_s = (c1_X − v_y0)/a_y0 = −t50, ADR-010/014).

    Estructura de la verdad (para detectar sesgos): ρ por nivel (`niveles_rho`, × ρ0), clima por juego, un efecto de
    lanzador α_j (SD `sigma_alpha` en log C_D) y **staffs asignados a parques locales**: cada parque tiene su
    plantel (`n_staff`), que lanza el `p_local` de los lanzamientos de sus juegos; los visitantes son los de los 3
    parques siguientes (anillo). Así el C_D medio del plantel carga en el parque si no se modela α_{j,k}.

    Calibración (Prop. 3′): en los juegos de `cubetas_sesgo` las posiciones se escalan por `lambda_escala` y los
    tiempos por `tau_reloj`, lo que deja el residuo c_g·g con c_g = λ/τ² − 1. `spinaxis_inferido=True` reemplaza
    `SpinAxis` por la dirección de la aceleración perpendicular medida (eje INFERIDO del movimiento).
    `calibracion_parques` {índice de parque: (λ, τ)} aplica la calibración por PARQUE (ver
    `esquema_calibracion_parques`) y sustituye a `cubetas_sesgo`. `n_jobs` > 1 integra los bloques en paralelo con
    joblib (un flujo aleatorio hijo por bloque: determinista, pero otra realización que `n_jobs=1`).

    Devuelve (DataFrame con las columnas de F2, verdad). El DataFrame trae las columnas de `pitches.parquet` que
    usa F2: ids, `year`, `altitude_category_h`, `familia`, `pitcher_throws_r`, `excluir_modelo`, 9P, `PitchTrajectoryXc1`,
    `SpinRate`, `SpinAxis`, `RelHeight`, `PlateLocSide`, `PlateLocHeight`.
    """
    rng = np.random.default_rng(semilla)
    niveles = {**NIVELES_RHO, **(niveles_rho or {})}
    cubetas = cubetas or CUBETAS_DEFECTO
    parques = [(cub, alt) for cub, spec in cubetas.items() for alt in spec["altitudes_m"]]
    n_p = len(parques)
    rho_parque = np.array([RHO_0 * niveles[c] * np.exp(rng.normal(0, sigma_parque)) for c, _ in parques])
    formas = list(_FORMAS_FISICA)

    # --- planteles: lanzadores con mano, repertorio, efecto α_j y descuadre de rapidez
    n_lanz = n_p * n_staff
    mano_r = rng.random(n_lanz) < 0.72
    alpha_j = rng.normal(0.0, sigma_alpha, n_lanz)
    dv_j = rng.normal(0.0, 2.0, n_lanz)
    uso = []
    for _ in range(n_lanz):
        k = int(rng.integers(3, 5))
        elegidas = rng.choice(len(formas), size=k, replace=False)
        w = np.zeros(len(formas))
        w[elegidas] = rng.dirichlet(np.ones(k) * 2.0)
        uso.append(w)
    uso = np.array(uso)
    staff = [np.arange(p * n_staff, (p + 1) * n_staff) for p in range(n_p)]

    # --- juegos y apariciones (lanzador × juego)
    nombres_cub = list(cubetas)
    pesos = np.array([cubetas[c]["peso_juegos"] for c in nombres_cub], dtype=float)
    pesos /= pesos.sum()
    parques_de = {c: [i for i, (cc, _) in enumerate(parques) if cc == c] for c in nombres_cub}
    g_idx, j_idx, k_idx = [], [], []
    juego_info = []
    for g in range(n_juegos):
        cub = nombres_cub[rng.choice(len(nombres_cub), p=pesos)]
        local = int(rng.choice(parques_de[cub]))
        visita = (local + int(rng.integers(1, 4))) % n_p
        clima = float(rng.normal(0.0, sigma_clima))
        anio = int(anios[rng.integers(0, len(anios))])
        juego_info.append({"parque": local, "cubeta": cub, "anio": anio, "rho": rho_parque[local] * np.exp(clima)})
        n_loc = round(p_local * apariciones_por_juego)
        quien = np.r_[rng.choice(staff[local], size=min(n_loc, n_staff), replace=False),
                      rng.choice(staff[visita], size=min(apariciones_por_juego - n_loc, n_staff), replace=False)]
        for j in quien:
            n_l = max(8, int(rng.poisson(lanzamientos_por_juego / apariciones_por_juego)))
            g_idx += [g] * n_l
            j_idx += [int(j)] * n_l
            k_idx += list(rng.choice(len(formas), size=n_l, p=uso[j]))
    g_idx, j_idx, k_idx = (np.array(x) for x in (g_idx, j_idx, k_idx))
    n = len(g_idx)
    rho_g = np.array([ji["rho"] for ji in juego_info])
    rho_i = rho_g[g_idx]
    if calibracion_parques is None:
        sesgado_g = np.array([ji["cubeta"] in cubetas_sesgo for ji in juego_info])
        lam_g = np.where(sesgado_g, lambda_escala, 1.0)
        tau_g = np.where(sesgado_g, tau_reloj, 1.0)
    else:
        lam_g = np.array([calibracion_parques.get(ji["parque"], (1.0, 1.0))[0] for ji in juego_info])
        tau_g = np.array([calibracion_parques.get(ji["parque"], (1.0, 1.0))[1] for ji in juego_info])
    c_juego = lam_g / tau_g**2 - 1.0
    lam_i, tau_i = lam_g[g_idx], tau_g[g_idx]

    # --- estado de liberación, giro y coeficientes por lanzamiento
    par = np.array([_FORMAS_FISICA[formas[k]] for k in k_idx])
    mph = (par[:, 0] + dv_j[j_idx] + rng.normal(0, 1.2, n))
    v_ms = mph * 0.44704
    x_r = np.where(mano_r[j_idx], 1.0, -1.0) * np.abs(rng.normal(2.0, 0.4, n)) * FT_M
    z_r = rng.normal(5.9, 0.3, n) * FT_M
    y_r = rng.normal(54.5, 0.25, n) * FT_M
    av = np.radians(par[:, 5] + rng.normal(0, 1.0, n))
    ah = np.radians(rng.normal(0, 0.7, n)) - np.arctan2(x_r, y_r)
    v0 = np.column_stack([v_ms * np.cos(av) * np.sin(ah), -v_ms * np.cos(av) * np.cos(ah), v_ms * np.sin(av)])
    r0 = np.column_stack([x_r, y_r, z_r])
    theta = par[:, 3] + rng.normal(0, 6.0, n)
    theta = np.where(mano_r[j_idx], theta, 360.0 - theta) % 360.0
    v_hat = v0 / np.linalg.norm(v0, axis=1)[:, None]
    n0 = direccion_magnus(theta, v_hat)
    omega_hat = np.cross(v_hat, n0)
    spin_rpm = par[:, 1] * (1.0 + rng.normal(0, 0.04, n))
    efic = np.clip(par[:, 2] + rng.normal(0, 0.04, n), 0.1, 1.0)
    omega_t = efic * spin_rpm * RPM_RADS
    cd = par[:, 4] * np.exp(alpha_j[j_idx] + rng.normal(0, sigma_cd_lanzamiento, n))

    # --- integración por bloques y ajuste 9P sobre posiciones con ruido
    dt, paso = 0.001, round(1000.0 / tasa_muestreo_hz)
    inicios = list(range(0, n, bloque))
    sls = [slice(ini, min(ini + bloque, n)) for ini in inicios]
    if n_jobs == 1:                                 # serie: un solo flujo del generador (reproduce la sintética histórica)
        rngs = [rng] * len(sls)
        salidas = [_ajustar_bloque(r0[sl], v0[sl], omega_hat[sl], omega_t[sl], cd[sl], rho_i[sl], lam_i[sl], tau_i[sl],
                                   rg, dt, paso, sigma_pos_m) for sl, rg in zip(sls, rngs, strict=True)]
    else:                                           # paralelo: un flujo hijo por bloque (determinista, otra realización)
        from joblib import Parallel, delayed
        rngs = rng.spawn(len(sls))
        salidas = Parallel(n_jobs=n_jobs)(
            delayed(_ajustar_bloque)(r0[sl], v0[sl], omega_hat[sl], omega_t[sl], cd[sl], rho_i[sl], lam_i[sl], tau_i[sl],
                                     rg, dt, paso, sigma_pos_m) for sl, rg in zip(sls, rngs, strict=True))
    coef = np.concatenate([o[0] for o in salidas])  # [lanzamiento, orden c0..c2, eje x,y,z] en ft y s (reloj medido)
    t_vuelo = np.concatenate([o[1] for o in salidas])
    c0, c1, c2 = coef[:, 0, :], coef[:, 1, :], coef[:, 2, :]
    t50 = _raiz_pequena(c0[:, 1] - 50.0, c1[:, 1], c2[:, 1])           # instante en que y = 50 ft (reloj medido)
    r9 = c0 + c1 * t50[:, None] + c2 * t50[:, None] ** 2
    v9 = c1 + 2 * c2 * t50[:, None]
    a9 = 2 * c2
    tp_rel = _raiz_pequena(c0[:, 1] - Y_FRENTE_PLATO_FT, c1[:, 1], c2[:, 1])
    pos_plato = c0 + c1 * tp_rel[:, None] + c2 * tp_rel[:, None] ** 2

    # --- columnas observables
    spin_obs = spin_rpm * (1.0 + rng.normal(0, 0.01, n))
    axis_obs = (theta + rng.normal(0, 3.0, n)) % 360.0
    if spinaxis_inferido:
        a_t = a9 * FT_M + np.array([0.0, 0.0, G_SI])
        vh = v9 / np.linalg.norm(v9, axis=1)[:, None]
        perp = a_t - np.einsum("ij,ij->i", a_t, vh)[:, None] * vh
        nh = perp / np.linalg.norm(perp, axis=1)[:, None]
        axis_obs = np.degrees(np.arctan2(nh[:, 0] / SIGNO_MAGNUS_X, -nh[:, 2])) % 360.0
    anio_i = np.array([ji["anio"] for ji in juego_info])[g_idx]
    cub_i = np.array([ji["cubeta"] for ji in juego_info])[g_idx]
    df = pl.DataFrame({
        "game_anon_id": [f"game_{g + 1:06d}" for g in g_idx],
        "pitcher_anon_id": [f"pitcher_{j + 1:05d}" for j in j_idx],
        "parque_id": [f"park_{juego_info[g]['parque'] + 1:02d}" for g in g_idx],
        "year": anio_i, "altitude_category_h": cub_i, "familia": [formas[k] for k in k_idx],
        "pitcher_throws_r": mano_r[j_idx], "excluir_modelo": np.zeros(n, dtype=bool),
        "x0": r9[:, 0], "y0": r9[:, 1], "z0": r9[:, 2], "vx0": v9[:, 0], "vy0": v9[:, 1], "vz0": v9[:, 2],
        "ax0": a9[:, 0], "ay0": a9[:, 1], "az0": a9[:, 2], "PitchTrajectoryXc1": c1[:, 1],
        "SpinRate": spin_obs, "SpinAxis": axis_obs, "RelHeight": c0[:, 2],
        "PlateLocSide": -pos_plato[:, 0], "PlateLocHeight": pos_plato[:, 2],
    })
    log_ref = float(np.mean([np.log(ji["rho"]) for ji in juego_info if ji["cubeta"] == "No Altitude"]))
    verdad = {
        "juegos": [f"game_{g + 1:06d}" for g in range(n_juegos)],
        "cubeta_juego": [ji["cubeta"] for ji in juego_info], "parque_juego": [ji["parque"] for ji in juego_info],
        "rho_juego": rho_g, "delta_verdad": np.log(rho_g) - log_ref,
        "alpha_j": alpha_j, "c_g": c_juego, "lambda": lambda_escala, "tau": tau_reloj,
        "cubetas_sesgo": tuple(cubetas_sesgo) if calibracion_parques is None else (),
        "parques": [{"cubeta": c, "altitud_m": a} for c, a in parques],
        "calibracion_parques": {int(k): tuple(v) for k, v in (calibracion_parques or {}).items()},
        "niveles_rho": niveles, "sigma_pos_m": sigma_pos_m, "sigma_alpha": sigma_alpha,
        "t_s": -t50, "t_vuelo": t_vuelo, "n_lanzamientos": n, "spinaxis_inferido": spinaxis_inferido,
        "signo_magnus_x": SIGNO_MAGNUS_X,
    }
    return df, verdad
