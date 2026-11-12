"""Vista 3: historial de predicciones con filtros.

El historial es la memoria del sistema: cada /predict y cada lote quedan aquí,
con la probabilidad que los disparó y si la alerta se confirmó. Los filtros
existen para poder contar una historia en la demo ("mira las últimas dos horas
de tráfico DoS"), no para adornar.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero.ui import datos, estilos, graficas

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]


def render() -> None:
    api = datos.api_actual()
    estilos.encabezado(
        "Historial de predicciones",
        "Todo lo que la API ha analizado y guardado. El origen distingue una "
        "consulta individual de una carga por lote; la columna Alerta dice si "
        "Telegram confirmó el mensaje.",
    )

    estado = datos.salud(api)
    if estado is None:
        estilos.bloque("La API no responde.", "Sin servicio no hay historial que leer.",
                       tono="aviso")
        return

    controles = st.columns([1, 1, 1.4, 1.2], gap="medium")
    limite = controles[0].selectbox("Registros leídos", [100, 250, 500, 1000], index=1)
    origen = controles[1].selectbox("Origen", ["todos", "api", "api-lote"])
    clases = controles[2].multiselect("Clases", CLASES, default=[],
                                     placeholder="Todas las clases")
    if controles[3].button("Actualizar", key="btn_hist_refrescar"):
        datos.invalidar()

    completo = datos.historial_df(api, limite)
    if completo.empty:
        st.info("El historial está vacío. Analiza una conexión para empezar.")
        return

    vista = completo.copy()
    if origen != "todos":
        vista = vista[vista["origen"] == origen]
    if clases:
        vista = vista[vista["clase"].isin(clases)]
    if vista.empty:
        st.info("Ningún registro coincide con esos filtros.")
        return

    umbral = estado.get("umbral_decision")
    ataques = int(vista["es_ataque"].sum())
    confirmadas = int(vista["alerta_enviada"].sum())
    estilos.banda(
        "Historial de predicciones",
        f"{len(vista):,} registros tras el filtro, de {len(completo):,} leídos "
        f"({min(limite, len(completo)):,} máximo por consulta).",
        [
            (f"{len(vista):,}", "Registros", "tras aplicar los filtros"),
            (f"{ataques:,}", "Ataques", "es_ataque = verdadero"),
            (f"{100 * ataques / max(1, len(vista)):.1f} %", "Tasa de ataque", "del conjunto filtrado"),
            (f"{confirmadas:,}", "Alertas enviadas", "confirmadas por Telegram"),
            (f"{vista['clase'].nunique()}", "Clases distintas", ", ".join(sorted(vista["clase"].unique()))),
        ],
    )

    estilos.seccion("1", "Probabilidad de ataque en el tiempo",
                    f"umbral de decisión {umbral}")
    st.altair_chart(graficas.serie_probabilidad(vista, umbral), width="stretch")
    estilos.fuente(
        "Cada punto es una predicción en orden de llegada; los rojos superaron el umbral. "
        "Una línea que se pega al umbral significa un modelo indeciso en ese tramo."
    )

    estilos.seccion("2", "Distribución", "por clase y por origen")
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        conteo_clase = (
            vista.groupby("clase", observed=True).size().reset_index(name="registros")
        )
        conteo_clase["clase"] = pd.Categorical(conteo_clase["clase"], CLASES, ordered=True)
        conteo_clase = conteo_clase.sort_values("clase")
        conteo_clase["etiqueta"] = conteo_clase["clase"].astype(str)
        st.altair_chart(
            graficas.barras_horizontales(conteo_clase, "etiqueta", "registros",
                                          "Predicciones"),
            width="stretch",
        )
    with derecha:
        conteo_origen = (
            vista.groupby("origen", observed=True).size().reset_index(name="registros")
        )
        st.altair_chart(
            graficas.barras_horizontales(conteo_origen, "origen", "registros",
                                          "Predicciones", color=graficas.VERDE_CLARO),
            width="stretch",
        )
        estilos.fuente(
            "api = consulta individual; api-lote = carga de CSV. "
            "Si todo viene de api-lote, la demo no ha ejercitado el camino de una sola fila."
        )

    estilos.seccion("3", "Registros", f"{len(vista):,} filas")
    estilos.tabla(
        [{
            "ID": int(f.id),
            "Hora (UTC)": f.hora,
            "Origen": f.origen,
            "Clase": f.clase,
            "p(ataque)": f"{f.probabilidad_ataque:.4f}",
            "p(clase)": f"{float(f.probabilidad_clase):.4f}",
            "Modelo": f.modelo,
            "Alerta": "sí" if f.alerta_enviada else "no",
        } for f in vista.sort_values("id", ascending=False).head(60).itertuples()],
        ["ID", "Hora (UTC)", "Origen", "Clase", "p(ataque)", "p(clase)", "Modelo", "Alerta"],
        numericas=("ID", "p(ataque)", "p(clase)"), fuertes=("Clase",),
    )
    if len(vista) > 60:
        st.caption("Se muestran los 60 más recientes. La descarga trae el conjunto filtrado completo.")

    with st.expander("Ver las 41 características de un registro"):
        registro = st.selectbox("ID", vista["id"].tolist(), index=0)
        fila = vista.loc[vista["id"] == registro].iloc[0]
        st.json(fila.get("features") or {}, expanded=False)

    st.download_button(
        "Descargar la vista filtrada (CSV, sin características)",
        vista.drop(columns=["features", "momento", "etiqueta"], errors="ignore")
        .to_csv(index=False).encode("utf-8"),
        file_name="historial_red_centinela.csv",
        mime="text/csv",
    )
