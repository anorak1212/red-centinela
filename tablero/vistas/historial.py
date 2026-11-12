"""Vista 3: historial de predicciones con filtros."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero.ui import datos, estilos

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]


def render() -> None:
    api = datos.api_actual()
    estilos.encabezado(
        "Historial",
        "Predicciones guardadas por la API. El origen distingue una consulta "
        "individual de una carga por lote; la columna Alerta dice si el mensaje "
        "de Telegram se confirmó.",
    )

    controles = st.columns([1, 1, 2], gap="medium")
    limite = controles[0].selectbox("Registros", [50, 100, 200, 500], index=1)
    origen = controles[1].selectbox("Origen", ["todos", "api", "api-lote"])
    if controles[2].button("Actualizar historial", key="btn_hist_refrescar"):
        datos.invalidar()

    filas = datos.historial(api, limite)
    if filas is None:
        estilos.bloque("La API no responde.", "Sin servicio no hay historial que leer.",
                       tono="aviso")
        return
    if not filas:
        st.info("El historial está vacío. Analiza una conexión para empezar.")
        return

    df = pd.DataFrame(filas)
    df["hora"] = pd.to_datetime(df["ts"], errors="coerce", utc=True).dt.strftime(
        "%d/%m/%Y %H:%M:%S"
    )
    if origen != "todos":
        df = df[df["origen"] == origen]
    if df.empty:
        st.info(f"No hay registros con origen '{origen}'.")
        return

    ataques = int(df["es_ataque"].sum())
    estilos.kpis([
        ("Mostrados", f"{len(df):,}", f"de {len(filas):,} leídos"),
        ("Ataques", f"{ataques:,}", "es_ataque = verdadero", 1),
        ("Alertas enviadas", f"{int(df['alerta_enviada'].sum()):,}", "confirmadas por Telegram"),
        ("Clases distintas", f"{df['clase'].nunique()}", ", ".join(sorted(df["clase"].unique()))),
    ], alerta=(1,))

    elegidas = st.multiselect(
        "Filtrar por clase", CLASES, default=[], placeholder="Todas las clases",
    )
    vista = df[df["clase"].isin(elegidas)] if elegidas else df
    st.caption(f"{len(vista):,} registros tras el filtro.")

    st.line_chart(
        vista.sort_values("id").set_index("id")["probabilidad_ataque"],
        height=200, color="#0f5c4a",
    )

    st.dataframe(
        vista[[
            "id", "hora", "origen", "modelo", "version_modelo", "clase",
            "probabilidad_ataque", "probabilidad_clase", "alerta_enviada",
        ]],
        hide_index=True,
        height=420,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "hora": st.column_config.TextColumn("Hora (UTC)"),
            "origen": st.column_config.TextColumn("Origen"),
            "modelo": st.column_config.TextColumn("Modelo"),
            "version_modelo": st.column_config.TextColumn("Ver."),
            "clase": st.column_config.TextColumn("Clase"),
            "probabilidad_ataque": st.column_config.ProgressColumn(
                "p(ataque)", min_value=0.0, max_value=1.0, format="%.4f"
            ),
            "probabilidad_clase": st.column_config.NumberColumn("p(clase)", format="%.4f"),
            "alerta_enviada": st.column_config.CheckboxColumn("Alerta"),
        },
    )

    with st.expander("Ver las 41 características de un registro"):
        registro = st.selectbox("ID", vista["id"].tolist(), index=0)
        features = vista.loc[vista["id"] == registro, "features"].iloc[0]
        st.json(features, expanded=False)

    st.download_button(
        "Descargar la vista (CSV, sin características)",
        vista.drop(columns=["features"]).to_csv(index=False).encode("utf-8"),
        file_name="historial_red_centinela.csv",
        mime="text/csv",
    )
