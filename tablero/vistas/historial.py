"""Vista 3: historial de predicciones con filtros.

El historial es la memoria del sistema: cada /predict y cada lote quedan aquí,
con la probabilidad que los disparó y si la alerta se confirmó. Los filtros
existen para poder contar una historia en la demo ("mira las últimas dos horas
de tráfico DoS"), no para adornar.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero import client
from tablero.ui import datos, estilos, graficas, preferencias

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]


def render() -> None:
    api = datos.api_actual()
    estilos.encabezado(
        "Historial de predicciones",
        "Todo lo que la API ha analizado y guardado. El origen distingue una "
        "consulta individual de una carga por lote, y la columna Alerta dice si "
        "Telegram confirmó el mensaje.",
    )

    estado = datos.salud(api)
    if estado is None:
        estilos.bloque("La API no responde.", "Sin servicio no hay historial que leer.",
                       tono="aviso")
        return

    with st.container(border=True):
        controles = st.columns([1, 1, 1.6, 0.9], gap="medium", vertical_alignment="bottom")
        # La API acepta como máximo 500 registros por consulta (/history?limit).
        opciones = [100, 250, client.HISTORIAL_MAXIMO]
        por_omision = preferencias.obtener("limite_historial")
        limite = controles[0].selectbox(
            "Registros leídos", opciones,
            index=opciones.index(por_omision) if por_omision in opciones else 1,
            help=f"La API devuelve como máximo {client.HISTORIAL_MAXIMO} por consulta.")
        origen = controles[1].selectbox("Origen", ["todos", "api", "api-lote"])
        clases = controles[2].multiselect("Clases", CLASES, default=[],
                                         placeholder="Todas las clases")
        if controles[3].button("Actualizar", key="btn_hist_refrescar",
                               icon=":material/refresh:", width="stretch"):
            datos.invalidar()
        filtros = st.columns([1.6, 1, 1], gap="medium", vertical_alignment="bottom")
        rango = filtros[0].slider("p(ataque) entre", 0.0, 1.0, (0.0, 1.0), step=0.01)
        buscar = filtros[1].text_input("Buscar ID", placeholder="p. ej. 42")
        solo_alerta = filtros[2].toggle("Solo con alerta enviada")

    completo = datos.historial_df(api, limite)
    if completo.empty:
        estilos.bloque(
            "El historial está vacío.",
            "Analiza una conexión o sube un CSV en <strong>Analizar</strong> para empezar.",
        )
        return

    vista = completo.copy()
    if origen != "todos":
        vista = vista[vista["origen"] == origen]
    if clases:
        vista = vista[vista["clase"].isin(clases)]
    vista = vista[vista["probabilidad_ataque"].between(rango[0], rango[1])]
    if solo_alerta:
        vista = vista[vista["alerta_enviada"].astype(bool)]
    if buscar.strip():
        if not buscar.strip().isdigit():
            st.warning("El ID debe ser un número entero.")
            return
        vista = vista[vista["id"] == int(buscar.strip())]
    if vista.empty:
        st.info("Ningún registro coincide con esos filtros.")
        return

    umbral = estado.get("umbral_decision")
    ataques = int(vista["es_ataque"].sum())
    confirmadas = int(vista["alerta_enviada"].sum())
    estilos.banda(
        "Historial filtrado",
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
        "Cada punto es una predicción en orden de llegada y los rojos superaron el umbral. "
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
                                          "Predicciones", color="claro"),
            width="stretch",
        )
        estilos.fuente(
            "api es una consulta individual y api-lote, una carga de CSV. "
            "Si todo viene de api-lote, la demo no ha ejercitado el camino de una sola fila."
        )

    estilos.seccion("3", "Simulador de umbral", "qué pasaría con otro punto de corte")
    _simulador(vista, umbral)

    estilos.seccion("4", "Registros", f"{len(vista):,} filas")
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

    exportable = vista.drop(columns=["features", "momento", "etiqueta"], errors="ignore")
    d1, d2, _ = st.columns([1.3, 1.3, 2])
    d1.download_button(
        "Descargar CSV (sin características)",
        exportable.to_csv(index=False).encode("utf-8"),
        file_name="historial_red_centinela.csv",
        mime="text/csv", icon=":material/download:", width="stretch",
    )
    d2.download_button(
        "Descargar JSON (con características)",
        vista.drop(columns=["momento", "etiqueta"], errors="ignore")
        .to_json(orient="records", force_ascii=False, indent=2).encode("utf-8"),
        file_name="historial_red_centinela.json",
        mime="application/json", icon=":material/data_object:", width="stretch",
    )


def _simulador(vista: pd.DataFrame, umbral) -> None:
    """Recuenta el historial con otro umbral, sin tocar la API.

    Sirve para responder en la defensa "¿y si bajan el umbral?": cuántas
    predicciones cambiarían de decisión. El umbral real del servicio sigue
    siendo el calibrado; esto es un cálculo local sobre p(ataque) ya guardada.
    """
    real = float(umbral) if umbral is not None else 0.5
    izquierda, derecha = st.columns([2, 3], gap="large")
    with izquierda:
        simulado = st.slider("Umbral simulado", 0.05, 0.95, min(0.95, max(0.05, real)), step=0.01,
                             key="umbral_simulado")
        p = vista["probabilidad_ataque"]
        actuales = int(vista["es_ataque"].sum())
        nuevos = int((p >= simulado).sum())
        suben = int(((p >= simulado) & ~vista["es_ataque"].astype(bool)).sum())
        bajan = int(((p < simulado) & vista["es_ataque"].astype(bool)).sum())
        estilos.kpis([
            ("Ataques con el umbral real", f"{actuales:,}", f"umbral {real:.2f}"),
            ("Ataques con el simulado", f"{nuevos:,}", f"umbral {simulado:.2f}",
             nuevos > actuales),
            ("Pasarían a ataque", f"{suben:,}", "hoy son normales"),
            ("Pasarían a normal", f"{bajan:,}", "hoy son ataques"),
        ])
    with derecha:
        st.altair_chart(graficas.histograma_probabilidad(vista, umbral, simulado),
                        width="stretch")
    estilos.bloque(
        "Simulación local.",
        "No cambia el umbral de la API ni el historial: recuenta las p(ataque) ya "
        "guardadas. Sin etiquetas reales no dice si el cambio acierta más, solo cuántas "
        "decisiones se moverían. El umbral oficial se calibró sobre el holdout interno.",
    )
