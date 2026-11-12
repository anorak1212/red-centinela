"""Controles de seguridad de la API (SEG-007).

Tres piezas, todas sin dependencias externas:

1. `LimiteTasa`  ventana deslizante por IP en memoria del proceso.
2. `LimiteCuerpo` middleware que rechaza cuerpos mayores al límite.
3. `cabeceras_seguridad` middleware que agrega cabeceras defensivas.

Ninguna de las tres requiere Redis. La API corre en una sola instancia del plan
gratuito, así que una ventana en memoria es suficiente y se documenta su límite:
si algún día se escala a varias instancias, cada una lleva su propio conteo.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


class LimiteTasa:
    """Ventana deslizante: máximo `maximo` peticiones por IP cada `ventana` s."""

    def __init__(self, maximo: int = 60, ventana: float = 60.0) -> None:
        self.maximo = maximo
        self.ventana = ventana
        self._eventos: dict[str, deque[float]] = defaultdict(deque)

    def permitir(self, clave: str) -> tuple[bool, int]:
        """Devuelve (permitido, segundos_de_espera)."""
        ahora = time.monotonic()
        eventos = self._eventos[clave]
        while eventos and ahora - eventos[0] > self.ventana:
            eventos.popleft()
        if len(eventos) >= self.maximo:
            espera = int(self.ventana - (ahora - eventos[0])) + 1
            return False, max(1, espera)
        eventos.append(ahora)
        return True, 0

    def limpiar(self) -> None:
        """Vacía el estado. Solo para pruebas."""
        self._eventos.clear()


def ip_cliente(request: Request) -> str:
    """IP del cliente respetando el proxy de Render."""
    reenviada = request.headers.get("x-forwarded-for", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def middleware_cuerpo(maximo_bytes: int):
    """Rechaza cuerpos declarados por encima del límite antes de parsearlos."""

    async def middleware(request: Request, call_next):
        declarado = request.headers.get("content-length")
        if declarado and declarado.isdigit() and int(declarado) > maximo_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Cuerpo demasiado grande. Máximo {maximo_bytes} bytes."},
            )
        return await call_next(request)

    return middleware


async def middleware_cabeceras(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    respuesta.headers.setdefault("Cache-Control", "no-store")
    return respuesta


def middleware_tasa(limitador: LimiteTasa, rutas: tuple[str, ...]):
    """Aplica el límite solo a las rutas indicadas."""

    async def middleware(request: Request, call_next):
        if request.url.path in rutas:
            permitido, espera = limitador.permitir(ip_cliente(request))
            if not permitido:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(espera)},
                    content={"detail": "Demasiadas peticiones. Espera antes de reintentar."},
                )
        return await call_next(request)

    return middleware
