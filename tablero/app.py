"""Tablero Streamlit de Red Centinela.

    streamlit run tablero/app.py

Consume la API REST (arranca con `uvicorn api.main:app`). Tres vistas:
predicción en vivo, carga de CSV por lote e historial, más un botón manual
de disparo de alertas (M5).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from alertas import telegram as alertas

from . import __version__
from .client import (
    COLUMNAS,
    ApiError,
    filas_desde_csv,
    historial,
    predecir,
    predecir_lote,
    salud,
)

st.set_page_config(page_title="Red Centinela", page_icon="🛰️", layout="wide")

SERVICIOS = ["http", "private", "domain_u", "ftp_data", "other", "smtp",
             "pop_3", "telnet", "ecr_i", "finger", "auth", "ftp", "ntp_u"]
PROTOCOLOS = ["tcp", "udp", "icmp"]
FLAGS = ["SF", "REJ", "S0", "S1", "S2", "S3", "RSTO", "RSTOS0", "SH", "RSTR"]

st.title("Red Centinela")
st.caption(f"Tablero de monitoreo de tráfico · v{__version__} · API: "
           f"{st.session_state.get('api_url', 'http://127.0.0.1:8000')}")


def estado_api() -> dict | None:
    try:
        return salud()
    except ApiError:
        return None


# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Configuración")
    api_url = st.text_input("URL de la API", value="http://127.0.0.1:8000")
    st.session_state["api_url"] = api_url

    estado = estado_api()
    if estado is None:
        st.error("API no disponible. Arranca:  `uvicorn api.main:app`")
        raise SystemExit
    st.success("API conectada")
    st.metric("Modelo productivo", "ensamble RF+KNN+SVM")
    st.metric("Umbral de decisión", estado.get("umbral_decision", "—"))
    metricas = estado.get("metricas_ultimas")
    if metricas:
        st.caption(f"AUC test {metricas.get('auc_roc_test', '—')} · "
                   f"macro-F1 {metricas.get('macro_f1_binario_test', '—')}")

    st.divider()
    st.subheader("Alertas (M5)")
    if st.button("Disparar alerta de prueba", use_container_width=True):
        ultimas = historial(1)
        if ultimas:
            p = ultimas[0]
            mensaje = (f"Red Centinela — Alerta: {p['es_ataque'] and 'ATAQUE' or 'normal'} "
                       f"con probabilidad {p['probabilidad']:.2f} (id {p['id']}, {p['ts']})")
        else:
            mensaje = "Red Centinela — prueba de alerta (sin predicciones aún)."
        resultado = alertas.enviar(mensaje)
        if resultado["ok"]:
            st.success("Alerta enviada por Telegram.")
        else:
            st.info(resultado["motivo"])

# ---------------------------------------------------------------- contenido
tabs = st.tabs(["Predicción en vivo", "Carga CSV por lote", "Historial"])

# --- Predicción en vivo ----------------------------------------------------
with tabs[0]:
    with st.form("form_en_vivo"):
        c1, c2, c3 = st.columns(3)
        features = {}
        for i, col in enumerate(COLUMNAS):
            destino = [c1, c2, c3][i % 3]
            if col in ("protocol_type", "service", "flag"):
                opciones = {"protocol_type": PROTOCOLOS, "service": SERVICIOS,
                            "flag": FLAGS}[col]
                features[col] = destino.selectbox(col, opciones, key=f"sel_{col}")
            else:
                features[col] = destino.number_input(
                    col, value=0.0, step=0.01, key=f"num_{col}", format="%.4f"
                )
        enviado = st.form_submit_button("Predecir", use_container_width=True)

    if enviado:
        try:
            r = predecir(features)
        except ApiError as e:
            st.error(str(e))
        else:
            if r["es_ataque"]:
                st.error(f"**{r['etiqueta'].upper()}** · probabilidad de ataque "
                         f"{r['probabilidad_ataque']:.4f} · id {r['id']}")
            else:
                st.success(f"**{r['etiqueta'].upper()}** · probabilidad de ataque "
                           f"{r['probabilidad_ataque']:.4f} · id {r['id']}")
            st.progress(min(1.0, r["probabilidad_ataque"]))
            st.caption(f"Modelo: {r['modelo']} · umbral {r['umbral']}")

# --- Carga CSV -------------------------------------------------------------
with tabs[1]:
    st.markdown("Sube un CSV con las **41 columnas** del NSL-KDD (mismo "
                "encabezado que `datasets/sample_trafico.csv`) y se predice "
                "todo el lote contra la API.")
    archivo = st.file_uploader("CSV de tráfico", type=["csv"])
    if archivo is not None:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(archivo.getbuffer())
            ruta = Path(tmp.name)
        try:
            filas = filas_desde_csv(ruta, max_filas=2_000)
        except ValueError as e:
            st.error(str(e))
        else:
            st.caption(f"{len(filas):,} filas válidas")
            st.dataframe(pd.DataFrame(filas).head(10), use_container_width=True)
            if st.button(f"Predecir lote ({len(filas):,} filas)", type="primary"):
                with st.spinner("Prediciendo..."):
                    try:
                        resultados = predecir_lote(filas)
                    except ApiError as e:
                        st.error(str(e))
                    else:
                        st.session_state["csv_resultados"] = pd.DataFrame([
                            {
                                "id": r["id"],
                                "etiqueta": r["etiqueta"],
                                "probabilidad_ataque": r["probabilidad_ataque"],
                            }
                            for r in resultados
                        ])

    if "csv_resultados" in st.session_state and st.session_state["csv_resultados"] is not None:
        df_res = st.session_state["csv_resultados"]
        st.subheader("Resultados del lote")
        ataques = int((df_res["etiqueta"] == "ataque").sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", len(df_res))
        c2.metric("Ataques", ataques)
        c3.metric("% ataque", f"{100 * ataques / max(1, len(df_res)):.1f}")
        st.bar_chart(df_res["etiqueta"].value_counts())
        st.dataframe(df_res, use_container_width=True)
        st.download_button(
            "Descargar resultados (CSV)", df_res.to_csv(index=False).encode(),
            file_name="resultado_lote.csv", mime="text/csv",
        )

# --- Historial -------------------------------------------------------------
with tabs[2]:
    if st.button("Actualizar historial", use_container_width=True):
        st.session_state["historial"] = None
    try:
        preds = historial(200)
    except ApiError as e:
        st.error(str(e))
    else:
        if preds:
            df_hist = pd.DataFrame(preds)
            c1, c2, c3 = st.columns(3)
            c1.metric("Predicciones", len(df_hist))
            c2.metric("Ataques", int(df_hist["es_ataque"].sum()))
            c3.metric("% ataque", f"{100 * df_hist['es_ataque'].mean():.1f}")
            st.subheader("Probabilidad de ataque en el tiempo (más reciente primero)")
            st.line_chart(df_hist.set_index("id")["probabilidad"])
            st.dataframe(df_hist.drop(columns=["features"]), use_container_width=True)
        else:
            st.info("Aún no hay predicciones en el historial.")