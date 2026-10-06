"""Entrada/salida y comparación de los tres formatos crudos.

- Lectura perezosa del parquet canónico (`polars.scan_parquet`).
- Lectores de `.pkl` (pandas) y `.rds` (pyreadr).
- `comparar_formatos()`: criterio de equivalencia 1-4 de ROADMAP §4-F0.0,
  por columna, cargando un archivo a la vez en memoria.
- `leer_diccionario()` / `perfilar_parquet()`: perfil del parquet contra
  `docs/diccionario.csv`.

`data/raw/` es de solo lectura (CLAUDE.md). Aquí nunca se escribe sobre ella.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

# Tokens que cuentan como nulo al homologar (criterio 4, ROADMAP §4-F0.0).
_NULOS = {"", "na", "nan", "none", "null", "<na>"}


# --------------------------------------------------------------------------
# Diccionario de columnas
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ColSpec:
    nombre: str
    definicion: str
    tipo: str            # integer / string / categorical / numeric / boolean...
    unidad_o_valores: str
    categoria: str
    rol: str             # feature_role: stuff_feature / target_only / ...
    usar_como_feature: str

    @property
    def es_numerica(self) -> bool:
        return self.tipo.lower().startswith(("numeric", "integer", "float"))

    @property
    def es_entera(self) -> bool:
        return self.tipo.lower().startswith("integer")

    @property
    def es_booleana(self) -> bool:
        return "boolean" in self.tipo.lower()

    @property
    def valores_enumerados(self) -> list[str] | None:
        """Valores permitidos si el diccionario los enumera; None si es abierto."""
        # Las numéricas traen una unidad (mph, feet, ...), no una enumeración.
        if self.es_numerica:
            return None
        v = self.unidad_o_valores.strip()
        low = v.lower()
        # Conjuntos abiertos, plantillas de formato o no enumerados en el diccionario.
        if not v or "#" in v or "dataset-specific" in low or "unique id" in low or "guid" in low:
            return None
        if any(tok in low for tok in ("yyyy", "hh:mm", "1 to n", "e.g.", "0/1", "true/false")):
            return None
        if "etc." in low:
            return None  # conjunto abierto (p. ej. hit_type)
        # Rango "a to b": no es enumeración exhaustiva de etiquetas.
        if re.fullmatch(r"\s*-?\d+\s+to\s+-?\d+\s*", v):
            return None
        partes = [p.strip() for p in v.split(",") if p.strip()]
        return partes or None

    @property
    def rango_entero(self) -> tuple[int, int] | None:
        v = self.unidad_o_valores.strip()
        m = re.fullmatch(r"\s*(-?\d+)\s+to\s+(-?\d+)\s*", v)
        if m:
            return int(m.group(1)), int(m.group(2))
        if re.fullmatch(r"\s*-?\d+(\s*,\s*-?\d+)+\s*", v):  # "0, 1, 2"
            nums = [int(x) for x in re.findall(r"-?\d+", v)]
            return min(nums), max(nums)
        return None


def leer_diccionario(ruta: str | Path) -> list[ColSpec]:
    df = pl.read_csv(ruta)
    specs = []
    for r in df.iter_rows(named=True):
        specs.append(ColSpec(
            nombre=r["column_name"],
            definicion=r.get("definition", "") or "",
            tipo=r.get("data_type", "") or "",
            unidad_o_valores=r.get("unit_or_values", "") or "",
            categoria=r.get("category", "") or "",
            rol=r.get("feature_role", "") or "",
            usar_como_feature=r.get("use_as_model_feature", "") or "",
        ))
    return specs


# --------------------------------------------------------------------------
# Lectores
# --------------------------------------------------------------------------
def leer_parquet_perezoso(ruta: str | Path) -> pl.LazyFrame:
    """Lectura perezosa, columnar, de la fuente canónica."""
    return pl.scan_parquet(ruta)


def leer_pkl(ruta: str | Path) -> pd.DataFrame:
    """Carga completa del .pkl con pandas.

    AVISO: `pickle` ejecuta código al cargar. Solo aceptable porque el archivo
    viene del organizador (ROADMAP §4-F0.0). Depende de la versión de pandas.
    """
    return pd.read_pickle(ruta)


def leer_rds(ruta: str | Path) -> pd.DataFrame:
    """Carga completa del .rds con pyreadr."""
    import pyreadr
    res = pyreadr.read_r(str(ruta))
    # Un .rds trae un solo objeto, bajo la clave None.
    clave = None if None in res else next(iter(res))
    return res[clave]


def _cargar_para_comparar(ruta: str | Path) -> pd.DataFrame:
    """Carga un formato a pandas, listo para comparar un archivo a la vez."""
    ruta = Path(ruta)
    ext = ruta.suffix.lower()
    if ext == ".parquet":
        return pd.read_parquet(ruta)
    if ext == ".pkl":
        return leer_pkl(ruta)
    if ext == ".rds":
        return leer_rds(ruta)
    raise ValueError(f"extensión no soportada: {ext}")


# --------------------------------------------------------------------------
# Comparación de equivalencia (criterio 1-4)
# --------------------------------------------------------------------------
def _norm_str(s: pd.Series) -> pd.Series:
    out = s.astype("object").where(~s.isna(), other=np.nan)
    out = out.map(lambda x: "" if (x is None or (isinstance(x, float) and math.isnan(x))) else str(x).strip())
    return out.map(lambda x: "\x00NULO" if x.lower() in _NULOS else x)


def _comparar_columna(a: pd.Series, b: pd.Series, tol: float) -> dict:
    """Compara una columna ya alineada por PitchUID. Devuelve estado y n_dif."""
    na_a, na_b = a.isna().to_numpy(), b.isna().to_numpy()
    if not np.array_equal(na_a, na_b):
        n = int((na_a != na_b).sum())
        return {"estado": "distinta", "n_dif": n, "motivo": "posiciones de nulos distintas"}
    num_a = pd.api.types.is_numeric_dtype(a)
    num_b = pd.api.types.is_numeric_dtype(b)
    if num_a and num_b:
        va = pd.to_numeric(a, errors="coerce").to_numpy(dtype="float64")
        vb = pd.to_numeric(b, errors="coerce").to_numpy(dtype="float64")
        m = ~(na_a | na_b)
        if not m.any():
            return {"estado": "igual", "n_dif": 0}
        dif = np.abs(va[m] - vb[m])
        tope = tol * np.maximum(1.0, np.abs(va[m]))
        malas = dif > tope
        n = int(malas.sum())
        return ({"estado": "igual", "n_dif": 0} if n == 0 else
                {"estado": "distinta", "n_dif": n, "motivo": f"máx|Δ|={float(dif.max()):.3e}"})
    # Categórica / texto: igualdad exacta tras normalizar a string y homologar nulos.
    sa, sb = _norm_str(a).to_numpy(), _norm_str(b).to_numpy()
    malas = sa != sb
    n = int(malas.sum())
    return {"estado": "igual", "n_dif": 0} if n == 0 else {"estado": "distinta", "n_dif": n}


def _comparar_dos(a: pd.DataFrame, b: pd.DataFrame, tol: float, clave: str = "PitchUID") -> dict:
    cols_a, cols_b = set(a.columns), set(b.columns)
    rep: dict = {
        "filas": {"a": len(a), "b": len(b), "igual": len(a) == len(b)},
        "columnas_solo_en_a": sorted(cols_a - cols_b),
        "columnas_solo_en_b": sorted(cols_b - cols_a),
        "por_columna": {},
    }
    # Criterio 1: PitchUID único y mismos conjuntos.
    rep["pitchuid"] = _chequear_pitchuid(a, b, clave)
    if not rep["pitchuid"]["comparables"]:
        rep["equivalentes"] = False
        return rep
    a = a.sort_values(clave).reset_index(drop=True)
    b = b.sort_values(clave).reset_index(drop=True)
    comunes = [c for c in a.columns if c in cols_b]
    todo_igual = rep["filas"]["igual"] and not rep["columnas_solo_en_a"] and not rep["columnas_solo_en_b"]
    for c in comunes:
        res = _comparar_columna(a[c], b[c], tol)
        rep["por_columna"][c] = res
        if res["estado"] != "igual":
            todo_igual = False
    rep["equivalentes"] = bool(todo_igual)
    return rep


def _chequear_pitchuid(a: pd.DataFrame, b: pd.DataFrame, clave: str) -> dict:
    if clave not in a.columns or clave not in b.columns:
        return {"comparables": False, "motivo": f"falta {clave} en algún formato"}
    ua, ub = a[clave], b[clave]
    unico_a, unico_b = ua.is_unique, ub.is_unique
    mismos = set(ua.dropna()) == set(ub.dropna())
    return {
        "comparables": bool(unico_a and unico_b and mismos),
        "unico_a": bool(unico_a), "unico_b": bool(unico_b),
        "mismos_ids": bool(mismos),
    }


def comparar_formatos(parquet: str | Path, pkl: str | Path | None,
                      rds: str | Path | None, tol: float = 1e-9) -> dict:
    """Compara el parquet canónico contra el .pkl y el .rds (criterio 1-4).

    Carga un formato a la vez en memoria además del parquet. Si un formato no
    existe o falla al cargar (p. ej. .pkl por versión de pandas), se reporta y
    se sigue (no aborta): el orquestador decide la fuente, el código no elige.
    """
    base = _cargar_para_comparar(parquet)
    out: dict = {"base": "parquet", "filas_base": len(base),
                 "columnas_base": int(base.shape[1]), "comparaciones": {}}
    for nombre, ruta in (("pkl", pkl), ("rds", rds)):
        if ruta is None or not Path(ruta).exists():
            out["comparaciones"][nombre] = {"estado": "ausente"}
            continue
        try:
            otro = _cargar_para_comparar(ruta)
        except Exception as e:  # noqa: BLE001 — se reporta y se sigue
            out["comparaciones"][nombre] = {"estado": "error_carga", "error": f"{type(e).__name__}: {e}"}
            continue
        out["comparaciones"][nombre] = {"estado": "comparado", **_comparar_dos(base, otro, tol)}
        del otro
    return out


# --------------------------------------------------------------------------
# Perfilado contra el diccionario
# --------------------------------------------------------------------------
def perfilar_parquet(parquet: str | Path, dicc: list[ColSpec], max_unicos: int = 50) -> dict:
    """Perfil columna a columna del parquet contra el diccionario.

    Para cada columna documentada: presencia, tipo observado, % nulos, rango
    (numéricas) o hasta `max_unicos` valores únicos (resto), y cumplimiento de
    unit_or_values. Lista también columnas no documentadas.
    """
    lf = leer_parquet_perezoso(parquet)
    cols_reales = lf.collect_schema().names()
    n = lf.select(pl.len()).collect().item()
    documentadas = {c.nombre for c in dicc}
    perfil: dict = {"n_filas": int(n), "columnas": {}, "no_documentadas": sorted(set(cols_reales) - documentadas)}
    for spec in dicc:
        if spec.nombre not in cols_reales:
            perfil["columnas"][spec.nombre] = {"presente": False}
            continue
        s = lf.select(spec.nombre).collect().to_series()
        nn = int(s.null_count())
        info: dict = {
            "presente": True,
            "tipo_observado": str(s.dtype),
            "tipo_diccionario": spec.tipo,
            "pct_nulos": round(100 * nn / n, 3) if n else None,
        }
        no_nulos = s.drop_nulls()
        if spec.es_numerica and no_nulos.len():
            try:
                info["rango"] = [float(no_nulos.min()), float(no_nulos.max())]
            except (TypeError, ValueError):
                pass
            ri = spec.rango_entero
            if ri is not None and no_nulos.len():
                fuera = int(((no_nulos < ri[0]) | (no_nulos > ri[1])).sum())
                info["cumple_rango"] = fuera == 0
                info["fuera_de_rango"] = fuera
        else:
            u = no_nulos.unique().to_list()
            info["n_unicos"] = len(u)
            if len(u) <= max_unicos:
                info["unicos"] = sorted(map(str, u))
            enum = spec.valores_enumerados
            if enum is not None:
                permitidos = {e.strip() for e in enum}
                fuera = sorted({str(x) for x in u} - permitidos)
                info["cumple_valores"] = not fuera
                if fuera:
                    info["valores_fuera"] = fuera[:max_unicos]
        perfil["columnas"][spec.nombre] = info
    perfil["faltantes"] = [c.nombre for c in dicc if c.nombre not in cols_reales]
    return perfil


# --------------------------------------------------------------------------
# Datos limpios de F0: directorio particionado por year (data/interim/pitches.parquet)
# --------------------------------------------------------------------------
def escribir_particionado(df: pl.DataFrame, ruta: str | Path, col: str = "year") -> dict:
    """Escribe `ruta/year=YYYY/part-0.parquet` (la columna `year` se conserva en cada archivo).

    Reemplaza el directorio entero: nunca quedan particiones de una corrida anterior.
    Devuelve las filas por partición (agregado, sin filas por lanzamiento).
    """
    import shutil
    ruta = Path(ruta)
    if ruta.exists():
        shutil.rmtree(ruta) if ruta.is_dir() else ruta.unlink()
    filas: dict = {}
    for (valor,), parte in df.partition_by(col, as_dict=True, maintain_order=True).items():
        destino = ruta / f"{col}={valor}"
        destino.mkdir(parents=True, exist_ok=True)
        parte.write_parquet(destino / "part-0.parquet", compression="zstd")
        filas[str(valor)] = parte.height
    return filas


def leer_pitches(ruta: str | Path) -> pl.LazyFrame:
    """Lectura perezosa de los datos limpios de F0 (directorio particionado o un solo parquet)."""
    ruta = Path(ruta)
    if ruta.is_dir():
        return pl.scan_parquet(sorted(ruta.glob("*/*.parquet")))
    return pl.scan_parquet(ruta)
