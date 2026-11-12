"""Preferencias del tablero que el usuario cambia en la vista Configuración.

Viven en la sesión del navegador (st.session_state): no hay base de datos del
tablero y no se guardan secretos. Cada preferencia afecta algo real:

- tema / acento / animaciones / densidad: el CSS y los colores de las gráficas
- intervalo_auto: cada cuánto se relee /history en Resumen
- limite_historial: registros que pide Historial al abrir
- tamano_lote: filas por petición a /predict/batch
- presentacion: letra grande y sin texto secundario, para proyectar
"""

from __future__ import annotations

import streamlit as st

ACENTOS = {
    "Azul centinela": ("#2450d6", "#1a3db0", "#ebf0fe", "#9db4f2"),
    "Índigo": ("#4f46e5", "#3f37c9", "#eef0ff", "#a5a1f5"),
    "Cian": ("#0e8aa8", "#0b6f88", "#e4f6fa", "#8fd3e3"),
    "Pizarra": ("#3b4a63", "#2a3649", "#eceff4", "#a3afc2"),
}
TEMAS = ("Claro", "Oscuro")
DENSIDADES = ("Cómoda", "Compacta")

POR_OMISION = {
    "tema": "Claro",
    "acento": "Azul centinela",
    "animaciones": True,
    "densidad": "Cómoda",
    "intervalo_auto": 15,
    "limite_historial": 250,
    "tamano_lote": 200,
    "presentacion": False,
}


def _estado() -> dict:
    if "preferencias" not in st.session_state:
        st.session_state["preferencias"] = dict(POR_OMISION)
    return st.session_state["preferencias"]


def obtener(clave: str):
    return _estado().get(clave, POR_OMISION[clave])


def fijar(clave: str, valor) -> None:
    _estado()[clave] = valor


def restablecer() -> None:
    st.session_state["preferencias"] = dict(POR_OMISION)


def oscuro() -> bool:
    try:
        return obtener("tema") == "Oscuro"
    except Exception:  # noqa: BLE001 - fuera de una sesión de Streamlit
        return False


def acento() -> tuple[str, str, str, str]:
    """(principal, oscuro, lavado, claro) del acento elegido."""
    try:
        return ACENTOS.get(obtener("acento"), ACENTOS["Azul centinela"])
    except Exception:  # noqa: BLE001
        return ACENTOS["Azul centinela"]
