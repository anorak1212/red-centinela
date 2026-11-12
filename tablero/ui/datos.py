"""Acceso a la API con caché de Streamlit.

Un rerun de Streamlit vuelve a ejecutar el script entero: si cada widget
pidiera /history otra vez, el tablero machacaría la API en cada clic. Aquí se
cachea por (URL, parámetro) con TTL corto y el botón "Actualizar" limpia todo.
"""

from __future__ import annotations

import streamlit as st

from tablero import client

TTL_CORTO = 10
TTL_METRICAS = 300


@st.cache_data(ttl=TTL_CORTO, show_spinner=False)
def salud(api: str, reverificar: bool = False) -> dict | None:
    cliente(api)
    try:
        return client.salud(reverificar=reverificar)
    except client.ApiError:
        return None


@st.cache_data(ttl=TTL_METRICAS, show_spinner=False)
def metricas(api: str) -> dict | None:
    cliente(api)
    try:
        return client.metricas()
    except client.ApiError:
        return None


@st.cache_data(ttl=TTL_CORTO, show_spinner=False)
def resumen(api: str) -> dict | None:
    cliente(api)
    try:
        return client.resumen_historial()
    except client.ApiError:
        return None


@st.cache_data(ttl=TTL_CORTO, show_spinner=False)
def historial(api: str, limit: int) -> list[dict] | None:
    cliente(api)
    try:
        return client.historial(limit)
    except client.ApiError:
        return None


@st.cache_data(ttl=TTL_CORTO, show_spinner=False)
def alertas(api: str) -> dict | None:
    cliente(api)
    try:
        return client.alertas_estado()
    except client.ApiError:
        return None


def cliente(api: str) -> None:
    """Alinea el cliente con la URL elegida antes de cualquier llamada."""
    client.configurar(api)


def api_actual() -> str:
    return st.session_state.get("api_url", client.api_url())


def invalidar() -> None:
    st.cache_data.clear()
