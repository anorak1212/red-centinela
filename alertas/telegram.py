"""Alertas por Telegram (M5, ALERT-010).

Reglas de operación:

- El token y el chat id se leen de las variables de entorno en cada envío, no al
  importar el módulo. Así el proceso puede arrancar sin credenciales y el
  operador solo necesita reiniciar para activarlas. El token nunca se escribe en
  un log ni en una respuesta HTTP (mitiga AM-10).
- Las detecciones se agrupan en una ventana de 10 segundos. Telegram limita los
  mensajes por minuto y una ráfaga de 50 predicciones no debe convertirse en 50
  mensajes. La ventana respeta el TTR: el peor caso es 10 s de espera más el
  tiempo de la petición HTTP, muy por debajo de los 60 s de ALERT-010.
- Un envío se considera exitoso solo si el Bot API responde `ok: true`. Si no hay
  credenciales, el estado es "no configurado": nunca se simula una entrega.

Prueba manual:

    python -m alertas.telegram
"""

from __future__ import annotations

import os
import threading
import time

import requests

API_BASE = "https://api.telegram.org"
VENTANA_AGRUPACION = 10.0
MAX_PENDIENTES = 50
TIMEOUT = 10
ESPERA_REINTENTO = 0.5

_estado = {
    "ultimo_envio_exitoso": None,
    "ultimo_error": None,
    "enviados": 0,
    "fallidos": 0,
    "agrupados": 0,
}

_pendientes: list[dict] = []
_lock = threading.Lock()
_ultimo_envio = 0.0
_hilo: threading.Thread | None = None
_on_envio = None  # gancho opcional: (tipo, ok, message_id) -> None
_on_confirmados = None  # gancho opcional: (ids_prediccion) -> None


def registrar_persistencia(gancho) -> None:
    """Registra cómo guardar cada intento real de envío.

    La API pasa aquí su función de persistencia, de modo que el contador de
    alertas sobreviva a los reinicios del servicio. El módulo de alertas no
    importa la base de datos: solo llama al gancho.
    """
    global _on_envio
    _on_envio = gancho


def registrar_confirmados(gancho) -> None:
    """Registra qué hacer cuando un lote se envía de verdad.

    Recibe los ids de las predicciones que viajaron en el mensaje agrupado, para
    que el historial marque esas filas como alertadas aunque el envío haya
    ocurrido después del request que las originó.
    """
    global _on_confirmados
    _on_confirmados = gancho


def _persistir(tipo: str, resultado: dict) -> None:
    if _on_envio is None:
        return
    try:
        _on_envio(tipo, bool(resultado.get("ok")), resultado.get("message_id"))
    except Exception:  # noqa: BLE001, S110 - la telemetría no rompe el envío
        pass


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
def _credenciales() -> tuple[str, str]:
    return (
        os.environ.get("REDCENTINELA_TELEGRAM_TOKEN", "").strip(),
        os.environ.get("REDCENTINELA_TELEGRAM_CHAT_ID", "").strip(),
    )


def configurado() -> bool:
    token, chat = _credenciales()
    return bool(token and chat)


def estado() -> dict:
    """Estado público del servicio de alertas. No expone credenciales."""
    return {
        "configurado": configurado(),
        "ventana_agrupacion_segundos": VENTANA_AGRUPACION,
        "pendientes": len(_pendientes),
        **_estado,
    }


# --------------------------------------------------------------------------
# Envío
# --------------------------------------------------------------------------
def _enviar_ahora(texto: str, tipo: str = "deteccion") -> dict:
    """Hace la petición al Bot API. Devuelve el resultado real y lo persiste."""
    token, chat = _credenciales()
    if not (token and chat):
        return {"ok": False, "estado": "no configurado",
                "detalle": "Faltan REDCENTINELA_TELEGRAM_TOKEN o "
                           "REDCENTINELA_TELEGRAM_CHAT_ID."}
    try:
        r = requests.post(
            f"{API_BASE}/bot{token}/sendMessage",
            json={"chat_id": chat, "text": texto, "disable_web_page_preview": True},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        # Un reintento con espera corta cubre el corte de red momentáneo.
        time.sleep(ESPERA_REINTENTO)
        try:
            r = requests.post(
                f"{API_BASE}/bot{token}/sendMessage",
                json={"chat_id": chat, "text": texto, "disable_web_page_preview": True},
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            # El mensaje de la excepción puede contener la URL con el token: se
            # registra solo el tipo de error.
            _estado["ultimo_error"] = type(exc).__name__
            _estado["fallidos"] += 1
            resultado = {"ok": False, "estado": "error de red",
                         "detalle": type(exc).__name__}
            _persistir(tipo, resultado)
            return resultado

    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {}
    if r.status_code == 200 and cuerpo.get("ok") is True:
        _estado["ultimo_envio_exitoso"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _estado["enviados"] += 1
        resultado = {"ok": True, "estado": "enviado",
                     "message_id": cuerpo.get("result", {}).get("message_id")}
        _persistir(tipo, resultado)
        return resultado

    _estado["fallidos"] += 1
    _estado["ultimo_error"] = f"HTTP {r.status_code}: {cuerpo.get('description', '')}"
    resultado = {"ok": False, "estado": "rechazado",
                 "detalle": f"HTTP {r.status_code}",
                 "descripcion": cuerpo.get("description", "")}
    _persistir(tipo, resultado)
    return resultado


def _volcar() -> dict:
    """Envía todo lo pendiente en un solo mensaje."""
    global _ultimo_envio
    with _lock:
        if not _pendientes:
            return {"ok": True, "estado": "sin pendientes", "enviados": 0}
        lote = _pendientes[:MAX_PENDIENTES]
        mensaje = "\n".join(item["texto"] for item in lote)
    resultado = _enviar_ahora(mensaje)
    if resultado.get("ok"):
        with _lock:
            del _pendientes[:len(lote)]
        _ultimo_envio = time.monotonic()
        resultado["agrupadas_en_el_lote"] = len(lote)
        resultado["ids_confirmados"] = [
            item["id"] for item in lote if item.get("id") is not None
        ]
        if _on_confirmados is not None and resultado["ids_confirmados"]:
            try:
                _on_confirmados(resultado["ids_confirmados"])
            except Exception:  # noqa: BLE001, S110 - el marcado no rompe el envío
                pass
    return resultado


def _bucle() -> None:
    """Vacía la cola cada ventana de agrupación mientras el proceso viva."""
    while True:
        time.sleep(VENTANA_AGRUPACION)
        try:
            _volcar()
        except Exception:  # noqa: BLE001 - un hilo de servicio no debe morir
            _estado["ultimo_error"] = "error inesperado en el vaciado"


def _asegurar_hilo() -> None:
    global _hilo
    if _hilo is not None and _hilo.is_alive():
        return
    _hilo = threading.Thread(target=_bucle, name="alertas-telegram", daemon=True)
    _hilo.start()


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------
def formatear(resultado: dict) -> str:
    """Mensaje legible de una detección."""
    clase = str(resultado.get("clase", "desconocida")).upper()
    prob = float(resultado.get("probabilidad_ataque", 0.0))
    cuando = time.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"RED CENTINELA | tráfico malicioso detectado\n"
        f"Clase: {clase}\n"
        f"Probabilidad de ataque: {prob:.2f}\n"
        f"Modelo: {resultado.get('modelo', 'RandomForest')} "
        f"{resultado.get('version_modelo', '')}\n"
        f"Hora: {cuando}"
    )


def notificar(resultado: dict, id_prediccion: int | None = None) -> dict:
    """Registra una detección para envío agrupado.

    Devuelve el estado inmediato. "agrupada" no significa entregada: significa
    que quedó en la ventana de 10 s. La entrega se confirma en `_volcar`, y el
    id viaja con el mensaje para poder marcar la fila correcta al confirmar.
    """
    if not configurado():
        return {"ok": False, "estado": "no configurado",
                "detalle": "alertas no configuradas"}
    _asegurar_hilo()
    with _lock:
        _pendientes.append({"texto": formatear(resultado), "id": id_prediccion})
        if len(_pendientes) > MAX_PENDIENTES:
            del _pendientes[: len(_pendientes) - MAX_PENDIENTES]
    _estado["agrupados"] += 1
    if time.monotonic() - _ultimo_envio >= VENTANA_AGRUPACION:
        # La ventana anterior ya cerró: se envía de inmediato.
        return _volcar()
    return {"ok": True, "estado": "agrupada", "ventana": VENTANA_AGRUPACION}


def enviar_prueba() -> dict:
    """Envía un mensaje de prueba y devuelve el resultado real del Bot API."""
    return _enviar_ahora(
        "RED CENTINELA | mensaje de prueba\n"
        "Si lees esto, el bot y el chat están configurados correctamente.\n"
        f"Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        tipo="prueba",
    )


if __name__ == "__main__":
    print(estado())
    print(enviar_prueba())
