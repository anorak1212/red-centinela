"""Cliente HTTP de la API Red Centinela para el tablero Streamlit.

El tablero NO carga modelos ni abre la base de datos: consume la API (diseño del
E14). Eso mantiene su despliegue en 3 dependencias y permite apuntarlo a la API
local o a la de producción sin tocar código.

Todas las funciones fallan con `ApiError` y un mensaje que dice qué pasó y qué
revisar; ninguna inventa datos cuando la API no responde.
"""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path

import requests

API_URL = os.environ.get("REDCENTINELA_API", "http://127.0.0.1:8000")
TIMEOUT = 20
LOTE_MAXIMO = 500
# /history acepta limit entre 1 y 500 (api/main.py). Pedir más devuelve 422.
HISTORIAL_MAXIMO = 500

# Columnas esperadas en los archivos CSV de carga (41 características del NSL-KDD).
COLUMNAS = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent", "hot",
    "num_failed_logins", "logged_in", "num_compromised", "root_shell",
    "su_attempted", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login",
    "count", "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate",
    "srv_rerror_rate", "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]
CATEGORICAS = {"protocol_type", "service", "flag"}
# Columnas de verdad conocida que puede traer un CSV de prueba. No se envían a
# la API: sirven para comparar la predicción con la etiqueta real.
VERDAD = ("label", "family")


class ApiError(RuntimeError):
    """La API no respondió o respondió con un error."""


def configurar(url: str) -> None:
    """Apunta el cliente a otra API (local, Render, túnel) sin reiniciar."""
    global API_URL
    API_URL = url.strip().rstrip("/") or API_URL


def api_url() -> str:
    return API_URL


def _url(ruta: str) -> str:
    return API_URL.rstrip("/") + ruta


def _get(ruta: str, **kwargs) -> requests.Response:
    try:
        return requests.get(_url(ruta), timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(f"Sin conexión con {API_URL} ({type(exc).__name__}).") from exc


def _post(ruta: str, **kwargs) -> requests.Response:
    try:
        return requests.post(_url(ruta), timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(f"Sin conexión con {API_URL} ({type(exc).__name__}).") from exc


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------
def salud(reverificar: bool = False, timeout: int = TIMEOUT) -> dict:
    """Estado del servicio, integridad de artefactos y resumen de métricas."""
    try:
        r = requests.get(
            _url("/health"), params={"reverificar": str(bool(reverificar)).lower()},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Sin conexión con {API_URL} ({type(exc).__name__}).") from exc
    if r.status_code != 200:
        raise ApiError(f"/health respondió {r.status_code}.")
    return r.json()


def esperar_api(segundos: int = 90) -> tuple[bool, float]:
    """Sondea /health hasta que la API responda. Devuelve (ok, segundos).

    "Responder" basta: una API en modo degradado (sin modelos) está despierta
    aunque no pueda predecir; el estado exacto lo muestra la barra lateral.
    Los planes gratuitos duermen el servicio: en la demo hay que despertarlo
    antes de proyectar, no durante.
    """
    inicio = time.perf_counter()
    while time.perf_counter() - inicio < segundos:
        try:
            salud(timeout=15)
            return True, time.perf_counter() - inicio
        except ApiError:
            time.sleep(min(5, max(0.0, segundos - (time.perf_counter() - inicio))))
    return False, time.perf_counter() - inicio


def sondear(ruta: str, timeout: int = 10) -> dict:
    """GET real a un endpoint: código HTTP y milisegundos medidos.

    Solo se usa con endpoints de lectura; los POST escriben en el historial o
    envían mensajes y no se disparan para "comprobar".
    """
    inicio = time.perf_counter()
    try:
        r = requests.get(_url(ruta), timeout=timeout)
    except requests.RequestException as exc:
        return {"ruta": ruta, "codigo": None, "ms": None, "error": type(exc).__name__}
    ms = (time.perf_counter() - inicio) * 1000
    return {"ruta": ruta, "codigo": r.status_code, "ms": ms, "error": None}


def sondear_url(url: str, timeout: int = 10) -> dict:
    """GET a una URL absoluta **sin seguir redirecciones**.

    Los servicios gratuitos contestan 303 hacia su pantalla de acceso cuando la
    app no es pública. Siguiendo la redirección se obtendría un 200 que diría
    "accesible" cuando en realidad pide iniciar sesión, así que se mide el
    primer código y el destino.
    """
    inicio = time.perf_counter()
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=False)
    except requests.RequestException as exc:
        return {"url": url, "codigo": None, "ms": None,
                "error": type(exc).__name__, "destino": None}
    return {
        "url": url,
        "codigo": r.status_code,
        "ms": (time.perf_counter() - inicio) * 1000,
        "error": None,
        "destino": r.headers.get("Location"),
    }


def metricas() -> dict:
    r = _get("/metrics")
    if r.status_code != 200:
        raise ApiError(f"/metrics respondió {r.status_code}.")
    return r.json()


def resumen_historial() -> dict:
    r = _get("/history/resumen")
    if r.status_code != 200:
        raise ApiError(f"/history/resumen respondió {r.status_code}.")
    return r.json()


def historial(limit: int = 200) -> list[dict]:
    limit = max(1, min(int(limit), HISTORIAL_MAXIMO))
    r = _get(f"/history?limit={limit}")
    if r.status_code != 200:
        raise ApiError(f"/history respondió {r.status_code}.")
    return r.json()["predicciones"]


def alertas_estado() -> dict:
    r = _get("/alertas/estado")
    if r.status_code != 200:
        raise ApiError(f"/alertas/estado respondió {r.status_code}.")
    return r.json()


def alerta_prueba() -> dict:
    """Pide a la API que envíe un mensaje de prueba al chat configurado."""
    r = _post("/alertas/prueba")
    if r.status_code != 200:
        raise ApiError(f"/alertas/prueba respondió {r.status_code}: {r.text[:160]}")
    return r.json()


# --------------------------------------------------------------------------
# Predicción
# --------------------------------------------------------------------------
def predecir(features: dict) -> dict:
    r = _post("/predict", json={"features": features})
    if r.status_code != 200:
        raise ApiError(_detalle(r, "/predict"))
    return r.json()


def predecir_lote(filas: list[dict], tamano: int = 200, progreso=None) -> list[dict]:
    """Predice por lotes para no rebasar el límite de la API ni el tiempo de espera."""
    tamano = max(1, min(int(tamano), LOTE_MAXIMO))
    resultados: list[dict] = []
    for i in range(0, len(filas), tamano):
        r = _post(
            "/predict/batch",
            json={"items": [{"features": f} for f in filas[i : i + tamano]]},
            timeout=TIMEOUT * 4,
        )
        if r.status_code != 200:
            raise ApiError(_detalle(r, "/predict/batch"))
        resultados.extend(r.json()["resultados"])
        if progreso is not None:
            progreso(min(1.0, len(resultados) / max(1, len(filas))))
    return resultados


def _detalle(r: requests.Response, ruta: str) -> str:
    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {}
    motivo = cuerpo.get("detail") if isinstance(cuerpo, dict) else None
    return f"{ruta} respondió {r.status_code}: {motivo or r.text[:160]}"


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def leer_csv(ruta: str | Path, max_filas: int = 2_000) -> tuple[list[dict], list[str | None]]:
    """Valida un CSV de tráfico y devuelve (filas de 41 features, familia real).

    La segunda lista trae la columna `family` cuando el archivo la incluye y
    `None` cuando no. Así el tablero puede calcular detección real por familia
    en vez de suponer que el archivo está bien clasificado.
    """
    ruta = Path(ruta)
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        lector = csv.DictReader(fh)
        if lector.fieldnames is None:
            raise ValueError("El CSV está vacío o no tiene encabezado.")
        columnas = [c.strip() for c in lector.fieldnames]
        faltan = [c for c in COLUMNAS if c not in columnas]
        sobras = [c for c in columnas if c not in COLUMNAS and c not in VERDAD]
        if faltan or sobras:
            partes = []
            if faltan:
                partes.append(f"faltan {len(faltan)} columnas ({', '.join(faltan[:5])})")
            if sobras:
                partes.append(f"sobran {len(sobras)} ({', '.join(sobras[:5])})")
            raise ValueError(
                "Encabezado inválido: " + " y ".join(partes)
                + f". Se esperan las {len(COLUMNAS)} columnas del NSL-KDD."
            )

        filas: list[dict] = []
        familias: list[str | None] = []
        trae_familia = "family" in columnas
        for numero, fila in enumerate(lector, start=1):
            if numero > max_filas:
                break
            limpia: dict = {}
            for col in COLUMNAS:
                valor = (fila.get(col) or "").strip()
                if col in CATEGORICAS:
                    if not valor:
                        raise ValueError(f"Fila {numero}: '{col}' está vacía.")
                    limpia[col] = valor.lower()
                else:
                    try:
                        limpia[col] = float(valor)
                    except ValueError as exc:
                        raise ValueError(
                            f"Fila {numero}: '{col}' no es un número ('{valor}')."
                        ) from exc
            filas.append(limpia)
            if trae_familia:
                familia = (fila.get("family") or "").strip().lower()
                familias.append(familia or None)
            else:
                familias.append(None)
    if not filas:
        raise ValueError("El CSV no tiene filas de datos.")
    return filas, familias


def filas_desde_csv(ruta: str | Path, max_filas: int = 2_000) -> list[dict]:
    """Compatibilidad: solo las 41 características."""
    return leer_csv(ruta, max_filas=max_filas)[0]


def ejemplos_etiquetados(ruta: str | Path) -> dict[str, dict]:
    """Un ejemplo real por familia desde un CSV con columna `family`.

    El tablero lo usa para el formulario de conexión individual: se predice una
    fila que existe en KDDTest+, no una inventada a mano.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return {}
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        lector = csv.DictReader(fh)
        elegidos: dict[str, dict] = {}
        for fila in lector:
            familia = (fila.get("family") or "").strip().lower()
            if not familia or familia in elegidos:
                continue
            limpia = {}
            for col in COLUMNAS:
                valor = (fila.get(col) or "").strip()
                limpia[col] = valor.lower() if col in CATEGORICAS else float(valor)
            elegidos[familia] = limpia
    return elegidos


def plantilla_csv() -> str:
    """Encabezado de las 41 columnas más una fila de ejemplo neutra."""
    ejemplo = ["tcp" if c == "protocol_type" else "http" if c == "service"
               else "sf" if c == "flag" else "0" for c in COLUMNAS]
    return ",".join(COLUMNAS) + "\n" + ",".join(ejemplo) + "\n"
