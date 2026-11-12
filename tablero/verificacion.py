"""Verificación medida del sistema (M1 a M6) y de los criterios del proyecto.

Esta capa no importa Streamlit ni abre conexiones: recibe lo que la vista midió
(por HTTP y por inspección de archivos) y devuelve el estado de cada módulo y de
cada criterio, siempre con el motivo y la cifra que lo sostienen.

La regla es una sola: un indicador se enciende cuando hay una medición que lo
respalda. Si no se midió, el estado es "no verificado", nunca "operando".
"""

from __future__ import annotations

import csv
import ipaddress
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

OPERANDO = "operando"
FALLA = "falla"
NO_VERIFICADO = "no verificado"

CUMPLIDO = "cumplido"
NO_CUMPLIDO = "no cumplido"

META_MACRO_F1 = 0.90
UMBRAL_LATENCIA_MS = 200.0

# Fila del NSL-KDD que el motor clasifica como normal con el umbral 0.41.
# Es la misma que usa scripts/smoke_prod.py: medir latencia con una fila de
# ataque dispararía una alerta de Telegram por cada llamada.
FILA_NORMAL = {
    "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "SF",
    "src_bytes": 232, "dst_bytes": 8153, "land": 0, "wrong_fragment": 0,
    "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 1,
    "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
    "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
    "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
    "count": 5, "srv_count": 5, "serror_rate": 0.0, "srv_serror_rate": 0.0,
    "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
    "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 30,
    "dst_host_srv_count": 255, "dst_host_same_srv_rate": 1.0,
    "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 0.03,
    "dst_host_srv_diff_host_rate": 0.04, "dst_host_serror_rate": 0.0,
    "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 0.0,
    "dst_host_srv_rerror_rate": 0.0,
}

DIRECCIONES_LOCALES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def es_url_publica(url: str | None) -> bool:
    """True solo si la URL es http(s) y el destino no es la propia máquina.

    Sirve para que DEPLOY-013 no se declare cumplido apuntando a 127.0.0.1,
    que es lo que hacía el texto fijo anterior de la vista Sistema.
    """
    if not url:
        return False
    partes = urlsplit(str(url).strip())
    if partes.scheme not in ("http", "https"):
        return False
    host = (partes.hostname or "").strip().lower()
    if not host or host in DIRECCIONES_LOCALES or host.endswith(".local"):
        return False
    try:
        direccion = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        direccion.is_private
        or direccion.is_loopback
        or direccion.is_link_local
        or direccion.is_reserved
    )


def percentil(valores: list[float], p: float = 0.95) -> float | None:
    """Percentil por rango más cercano. Con pocos datos es lo que hay: se dice n."""
    limpios = sorted(float(v) for v in valores if v is not None)
    if not limpios:
        return None
    p = min(1.0, max(0.0, float(p)))
    indice = math.ceil(p * len(limpios)) - 1
    return limpios[max(0, min(len(limpios) - 1, indice))]


def medir_latencia(predecir, fila=None, muestras: int = 5,
                   umbral_ms: float = UMBRAL_LATENCIA_MS) -> dict:
    """Cronometra N llamadas a /predict con una fila que debe salir normal.

    `predecir` es una función que recibe un dict de 41 características y
    devuelve la respuesta de la API. Se corta en la primera respuesta marcada
    como ataque: seguir mediría latencia a costa de enviar alertas.
    """
    fila = dict(FILA_NORMAL if fila is None else fila)
    tiempos: list[float] = []
    fallos = 0
    ultimo_error = None
    for _ in range(max(1, int(muestras))):
        inicio = time.perf_counter()
        try:
            respuesta = predecir(fila)
        except Exception as exc:  # noqa: BLE001 - el borde HTTP puede lanzar ApiError o cualquier otra
            # Se cuenta el fallo y se sigue midiendo: una llamada perdida no debe
            # invalidar las demás muestras.
            fallos += 1
            ultimo_error = f"{type(exc).__name__}: {exc}"[:160]
            continue
        tiempos.append((time.perf_counter() - inicio) * 1000)
        if isinstance(respuesta, dict) and respuesta.get("es_ataque"):
            return {
                "p95_ms": percentil(tiempos), "mediana_ms": statistics.median(tiempos),
                "n": len(tiempos), "fallos": fallos, "umbral_ms": umbral_ms,
                "error": "la fila de medición salió como ataque: se detuvo para no "
                         "generar alertas",
            }
    if not tiempos:
        return {
            "p95_ms": None, "mediana_ms": None, "n": 0, "fallos": fallos,
            "umbral_ms": umbral_ms,
            "error": ultimo_error or "ninguna petición completada",
        }
    return {
        "p95_ms": percentil(tiempos), "mediana_ms": statistics.median(tiempos),
        "n": len(tiempos), "fallos": fallos, "umbral_ms": umbral_ms,
        "error": ultimo_error,
    }


def inspeccionar_datasets(raiz: str | Path) -> dict:
    """Comprueba que los CSV de muestra del repositorio existen y traen 41 columnas.

    Es la evidencia medible de M1 desde el tablero: el repositorio y su EDA se
    materializan en estos archivos versionados.
    """
    raiz = Path(raiz)
    piezas: list[str] = []
    ok = True
    for nombre, minimo in (("sample_etiquetado.csv", 42), ("sample_trafico.csv", 41)):
        ruta = raiz / "datasets" / nombre
        if not ruta.exists():
            ok = False
            piezas.append(f"falta datasets/{nombre}")
            continue
        try:
            with ruta.open(newline="", encoding="utf-8-sig") as fh:
                lector = csv.reader(fh)
                cabecera = next(lector, [])
                filas = sum(1 for _ in lector)
        except OSError as exc:
            ok = False
            piezas.append(f"datasets/{nombre} ilegible ({type(exc).__name__})")
            continue
        if len(cabecera) < minimo:
            ok = False
            piezas.append(
                f"datasets/{nombre} con {len(cabecera)} columnas, se esperan {minimo} o más"
            )
        else:
            piezas.append(f"{nombre} {filas} filas")
    return {"ok": ok, "detalle": "; ".join(piezas) or "sin datasets versionados"}


def _macro_f1(metricas: dict | None, salud: dict | None) -> float | None:
    for fuente in (metricas, (salud or {}).get("metricas")):
        if not isinstance(fuente, dict):
            continue
        valor = (fuente.get("binario_kddtest") or {}).get("macro_f1")
        if valor is None:
            continue
        try:
            return float(valor)
        except (TypeError, ValueError):
            continue
    return None


def _modulo(ident: str, nombre: str, estado: str, motivo: str) -> dict:
    return {"id": ident, "nombre": nombre, "estado": estado, "motivo": motivo}


def _criterio(ident: str, nombre: str, exigencia: str, medido: str,
              estado: str, motivo: str = "") -> dict:
    return {
        "id": ident, "nombre": nombre, "exigencia": exigencia,
        "medido": medido, "estado": estado, "motivo": motivo,
    }


def verificar(
    *,
    api_url: str,
    tablero_url: str | None = None,
    salud: dict | None = None,
    metricas: dict | None = None,
    alertas: dict | None = None,
    endpoints: list[dict] | None = None,
    latencia: dict | None = None,
    tablero: dict | None = None,
    repositorio: dict | None = None,
    meta_macro_f1: float = META_MACRO_F1,
    umbral_latencia_ms: float = UMBRAL_LATENCIA_MS,
) -> dict:
    """Construye el estado de M1 a M6 y de los cinco criterios.

    Todos los argumentos son lo ya medido:
    `salud` es /health, `metricas` es /metrics, `alertas` es /alertas/estado,
    `endpoints` son los GET sondeados, `latencia` sale de `medir_latencia`,
    `tablero` de sondear su URL sin seguir redirecciones y `repositorio` de
    `inspeccionar_datasets`.
    """
    almacen = (salud or {}).get("almacen") or {}
    persistente = bool(almacen.get("persistente"))
    motor_almacen = almacen.get("motor") or "no declarado"
    publica = es_url_publica(api_url)
    vivo = bool(salud) and salud.get("status") == "ok"
    macro_f1 = _macro_f1(metricas, salud)
    umbral = (salud or {}).get("umbral_decision")

    modulos: list[dict] = []

    # M1: repositorio y EDA, medido sobre los CSV versionados.
    if repositorio is None:
        modulos.append(_modulo("M1", "Repositorio y EDA", NO_VERIFICADO,
                               "no se inspeccionaron los archivos del repositorio"))
    elif repositorio.get("ok"):
        modulos.append(_modulo("M1", "Repositorio y EDA", OPERANDO,
                               str(repositorio.get("detalle", ""))))
    else:
        modulos.append(_modulo("M1", "Repositorio y EDA", FALLA,
                               str(repositorio.get("detalle", "datasets incompletos"))))

    # M2: motor cargado e íntegro.
    if salud is None:
        modulos.append(_modulo("M2", "Motor de detección", NO_VERIFICADO,
                               "la API no respondió /health"))
    elif not salud.get("modelos_disponibles", False):
        modulos.append(_modulo("M2", "Motor de detección", FALLA,
                               "la API responde sin modelos cargados: /predict devuelve 503"))
    elif not salud.get("integridad_artefactos"):
        modulos.append(_modulo("M2", "Motor de detección", FALLA,
                               "los .joblib no coinciden con el manifiesto SHA-256"))
    else:
        modulos.append(_modulo(
            "M2", "Motor de detección", OPERANDO,
            f"Random Forest e Isolation Forest cargados, SHA-256 íntegro, "
            f"umbral {umbral if umbral is not None else 'sin datos'}",
        ))

    # M3: API y almacén persistente.
    if salud is None:
        modulos.append(_modulo("M3", "API REST", NO_VERIFICADO,
                               "la API no respondió /health"))
    elif not vivo:
        modulos.append(_modulo("M3", "API REST", FALLA,
                               f"la API responde en estado '{salud.get('status', '?')}'"))
    elif almacen and not persistente:
        modulos.append(_modulo(
            "M3", "API REST", FALLA,
            f"almacén {motor_almacen} no persistente: en producción el historial "
            "se pierde en cada reinicio",
        ))
    elif endpoints is None:
        modulos.append(_modulo("M3", "API REST", NO_VERIFICADO,
                               "no se sondearon los endpoints de lectura"))
    else:
        fallidos = [e for e in endpoints if e.get("codigo") != 200]
        if fallidos:
            detalle = ", ".join(
                f"{e.get('ruta')} ({e.get('codigo') or e.get('error') or 'sin respuesta'})"
                for e in fallidos
            )
            modulos.append(_modulo(
                "M3", "API REST", FALLA,
                f"{len(fallidos)} de {len(endpoints)} endpoints de lectura no respondieron "
                f"200: {detalle}",
            ))
        else:
            modulos.append(_modulo(
                "M3", "API REST", OPERANDO,
                f"{len(endpoints)} endpoints de lectura con 200, almacén "
                f"{motor_almacen}{' persistente' if persistente else ''}",
            ))

    # M4: tablero.
    if tablero is None:
        modulos.append(_modulo("M4", "Tablero Streamlit", NO_VERIFICADO,
                               "no se comprobó la URL del tablero"))
    elif tablero.get("codigo") == 200:
        modulos.append(_modulo("M4", "Tablero Streamlit", OPERANDO,
                               f"responde 200 en {tablero.get('url')}"))
    elif tablero.get("codigo") in (301, 302, 303, 307, 308):
        modulos.append(_modulo(
            "M4", "Tablero Streamlit", OPERANDO,
            f"responde {tablero.get('codigo')}; redirige a inicio de sesión, "
            "así que el acceso público queda para DEPLOY-013",
        ))
    elif tablero.get("codigo") is None:
        modulos.append(_modulo("M4", "Tablero Streamlit", NO_VERIFICADO,
                               f"sin respuesta de {tablero.get('url')} "
                               f"({tablero.get('error') or 'error de red'})"))
    else:
        modulos.append(_modulo("M4", "Tablero Streamlit", FALLA,
                               f"{tablero.get('url')} respondió {tablero.get('codigo')}"))

    # M5: alertas configuradas y con envío confirmado.
    if alertas is None:
        modulos.append(_modulo("M5", "Alertas Telegram", NO_VERIFICADO,
                               "la API no respondió /alertas/estado"))
    elif not alertas.get("configurado"):
        modulos.append(_modulo("M5", "Alertas Telegram", FALLA,
                               "sin token o chat_id: no hay envío posible"))
    elif int(alertas.get("enviados") or 0) > 0:
        modulos.append(_modulo(
            "M5", "Alertas Telegram", OPERANDO,
            f"{int(alertas.get('enviados') or 0)} envíos confirmados, "
            f"{int(alertas.get('fallidos') or 0)} fallidos",
        ))
    else:
        modulos.append(_modulo("M5", "Alertas Telegram", NO_VERIFICADO,
                               "configurado, pero sin envíos confirmados todavía"))

    # M6: despliegue público con almacén que sobrevive.
    if salud is None:
        modulos.append(_modulo("M6", "Despliegue y operación", NO_VERIFICADO,
                               "la API no respondió /health"))
    elif not publica:
        modulos.append(_modulo("M6", "Despliegue y operación", FALLA,
                               f"la API apunta a {api_url}: no es una URL pública"))
    elif not persistente:
        modulos.append(_modulo("M6", "Despliegue y operación", FALLA,
                               f"el almacén ({motor_almacen}) no persiste entre reinicios"))
    else:
        modulos.append(_modulo(
            "M6", "Despliegue y operación", OPERANDO,
            f"API pública en {urlsplit(api_url).hostname} con almacén "
            f"{motor_almacen} persistente",
        ))

    # Criterios.
    criterios: list[dict] = []

    if salud is None:
        criterios.append(_criterio(
            "Integridad SHA-256", "Integridad de artefactos",
            "los .joblib coinciden con el manifiesto",
            "sin datos", NO_VERIFICADO, "la API no respondió /health",
        ))
    elif salud.get("integridad_artefactos"):
        criterios.append(_criterio(
            "Integridad SHA-256", "Integridad de artefactos",
            "los .joblib coinciden con el manifiesto",
            "manifiesto verificado", CUMPLIDO,
        ))
    else:
        criterios.append(_criterio(
            "Integridad SHA-256", "Integridad de artefactos",
            "los .joblib coinciden con el manifiesto",
            "no verificados", NO_CUMPLIDO,
            "la API respondió con integridad_artefactos = false",
        ))

    if macro_f1 is None:
        criterios.append(_criterio(
            "PERF-003", "Macro-F1 sobre KDDTest+",
            f"≥ {meta_macro_f1:.2f}", "sin datos", NO_VERIFICADO,
            "no se pudo leer binario_kddtest.macro_f1",
        ))
    else:
        cumple = macro_f1 >= meta_macro_f1
        criterios.append(_criterio(
            "PERF-003", "Macro-F1 sobre KDDTest+",
            f"≥ {meta_macro_f1:.2f}", f"{macro_f1:.4f}",
            CUMPLIDO if cumple else NO_CUMPLIDO,
            "" if cumple else
            f"faltan {meta_macro_f1 - macro_f1:.4f}; KDDTest+ incluye familias que "
            "no están en el entrenamiento",
        ))

    if latencia is None:
        criterios.append(_criterio(
            "PERF-006", "Latencia p95 de /predict",
            f"≤ {umbral_latencia_ms:.0f} ms", "sin medir", NO_VERIFICADO,
            "no se cronometraron llamadas a /predict",
        ))
    elif latencia.get("p95_ms") is None:
        criterios.append(_criterio(
            "PERF-006", "Latencia p95 de /predict",
            f"≤ {umbral_latencia_ms:.0f} ms", "sin datos", NO_VERIFICADO,
            str(latencia.get("error") or "ninguna petición completada"),
        ))
    else:
        p95 = float(latencia["p95_ms"])
        cumple = p95 <= umbral_latencia_ms
        nota = f"{p95:.0f} ms p95 de n={latencia.get('n', 0)}"
        if latencia.get("fallos"):
            nota += f", {latencia['fallos']} fallos"
        if latencia.get("error"):
            nota += f" ({latencia['error']})"
        criterios.append(_criterio(
            "PERF-006", "Latencia p95 de /predict",
            f"≤ {umbral_latencia_ms:.0f} ms", nota,
            CUMPLIDO if cumple else NO_CUMPLIDO,
            "" if cumple else "medida en vivo con el servicio despierto",
        ))

    if alertas is None:
        criterios.append(_criterio(
            "ALERT-010", "Alerta enviada",
            "mensaje confirmado en el chat de Telegram",
            "sin datos", NO_VERIFICADO, "la API no respondió /alertas/estado",
        ))
    elif int(alertas.get("enviados") or 0) > 0:
        criterios.append(_criterio(
            "ALERT-010", "Alerta enviada",
            "mensaje confirmado en el chat de Telegram",
            f"{int(alertas.get('enviados') or 0)} enviados, "
            f"{int(alertas.get('fallidos') or 0)} fallidos",
            CUMPLIDO, str(alertas.get("ultimo_envio_exitoso") or ""),
        ))
    else:
        criterios.append(_criterio(
            "ALERT-010", "Alerta enviada",
            "mensaje confirmado en el chat de Telegram",
            "0 envíos", NO_CUMPLIDO,
            "el bot está configurado pero no hay un envío confirmado",
        ))

    partes_api = []
    if not publica:
        partes_api.append(f"la API apunta a {api_url}")
    elif salud is None:
        partes_api.append("la API no respondió")
    if tablero is None:
        partes_api.append("no se comprobó la URL del tablero")
    elif tablero.get("codigo") != 200:
        partes_api.append(
            f"el tablero respondió {tablero.get('codigo') or tablero.get('error')} en "
            f"{tablero.get('url')}"
        )
    if partes_api:
        criterios.append(_criterio(
            "DEPLOY-013", "URL pública",
            "API y tablero accesibles sin instalar nada",
            "no verificado" if not publica or tablero is None else "incompleto",
            NO_VERIFICADO if not publica or tablero is None else NO_CUMPLIDO,
            "; ".join(partes_api),
        ))
    else:
        criterios.append(_criterio(
            "DEPLOY-013", "URL pública",
            "API y tablero accesibles sin instalar nada",
            f"{urlsplit(api_url).hostname} y {urlsplit(str(tablero_url)).hostname}",
            CUMPLIDO,
        ))

    return {
        "momento": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_url": api_url,
        "tablero_url": tablero_url,
        "api_publica": publica,
        "modulos": modulos,
        "criterios": criterios,
        "operando": sum(1 for m in modulos if m["estado"] == OPERANDO),
        "total_modulos": len(modulos),
        "macro_f1": macro_f1,
        "umbral": umbral,
    }
