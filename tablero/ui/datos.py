"""Acceso a la API con caché de Streamlit.

Un rerun de Streamlit vuelve a ejecutar el script entero: si cada widget
pidiera /history otra vez, el tablero machacaría la API en cada clic. Aquí se
cachea por (URL, parámetro) con TTL corto y el botón "Actualizar" limpia todo.
"""

from __future__ import annotations

import pandas as pd
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


@st.cache_data(ttl=TTL_CORTO, show_spinner=False)
def historial_df(api: str, limit: int) -> pd.DataFrame:
    """Historial ya normalizado para graficar: hora, etiqueta y momento.

    Se hace aqui y no en cada vista para que el area de actividad y la tabla
    del historial cuenten exactamente lo mismo.
    """
    cliente(api)
    try:
        filas = client.historial(limit)
    except client.ApiError:
        return pd.DataFrame()
    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    df["momento"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    df["hora"] = df["momento"].dt.strftime("%d/%m %H:%M:%S")
    df["etiqueta"] = df["es_ataque"].map({True: "ataque", False: "normal"})
    df["probabilidad_ataque"] = df["probabilidad_ataque"].astype(float)
    return df.sort_values("id").reset_index(drop=True)


def cliente(api: str) -> None:
    """Alinea el cliente con la URL elegida antes de cualquier llamada."""
    client.configurar(api)


def api_actual() -> str:
    return st.session_state.get("api_url", client.api_url())


def invalidar() -> None:
    st.cache_data.clear()
