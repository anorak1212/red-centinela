"""Vista 2: analizar una conexión o un archivo completo."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from tablero import client
from tablero.ui import datos, estilos

RAIZ = Path(__file__).resolve().parents[2]
MUESTRA = RAIZ / "datasets" / "sample_etiquetado.csv"

DESCRIPCION_CORTA = "Una fila del NSL-KDD enviada a /predict, o un lote entero a /predict/batch."


def render() -> None:
    estilos.encabezado(
        "Analizar tráfico",
        "Cada análisis se guarda en el historial y, si resulta ataque, dispara la "
        "alerta. No hay modo de prueba: lo que se ve aquí es lo que quedó registrado.",
    )
    estado = datos.salud(datos.api_actual())
    if estado is None:
        estilos.bloque(
            "La API no responde.",
            "No se puede predecir sin servicio. Despiértalo desde la barra lateral.",
            tono="aviso",
        )
        return

    individual, lote = st.tabs(["Conexión individual", "Archivo CSV"])
    with individual:
        _conexion_individual()
    with lote:
        _archivo_csv()


# --------------------------------------------------------------------------
# Conexión individual
# --------------------------------------------------------------------------
def _conexion_individual() -> None:
    ejemplos = client.ejemplos_etiquetados(MUESTRA)
    familias = [f for f in ("normal", "dos", "probe", "r2l", "u2r") if f in ejemplos]

    if familias:
        eleccion = st.selectbox(
            "Fila de partida",
            familias,
            help="Cada opción es una conexión real de KDDTest+ con su familia "
                 "verdadera. Se puede editar el JSON antes de predecir.",
        )
        base = dict(ejemplos[eleccion])
    else:
        eleccion = "manual"
        base = {c: (0.0 if c not in client.CATEGORICAS else "") for c in client.COLUMNAS}
        st.warning(
            "No se encontró datasets/sample_etiquetado.csv: escribe las 41 "
            "características a mano."
        )

    with st.expander("Características enviadas (41 columnas)", expanded=False):
        texto = st.text_area(
            "JSON editable",
            value=json.dumps(base, indent=2, ensure_ascii=False),
            height=300,
            label_visibility="collapsed",
        )

    col1, col2 = st.columns([1, 3])
    predecir = col1.button("Predecir", type="primary", key="btn_predecir_uno")
    if familias:
        col2.caption(
            f"Etiqueta real de esta fila: **{eleccion}**. Útil para mostrar en la "
            "demo si el modelo acierta o confunde la familia."
        )

    if predecir:
        try:
            features = json.loads(texto)
        except json.JSONDecodeError as exc:
            st.error(f"El JSON no es válido: {exc.msg} (línea {exc.lineno}).")
            return
        faltan = [c for c in client.COLUMNAS if c not in features]
        if faltan:
            st.error(f"Faltan {len(faltan)} características: {', '.join(faltan[:6])}.")
            return

        with st.spinner("Consultando la API..."):
            try:
                r = client.predecir({c: features[c] for c in client.COLUMNAS})
            except client.ApiError as exc:
                st.error(str(exc))
                return
        datos.invalidar()

        if r["es_ataque"]:
            st.error(f"**ATAQUE** · familia {r['clase'].upper()} · "
                     f"p(ataque) = {r['probabilidad_ataque']:.4f}")
        else:
            st.success(f"**NORMAL** · p(ataque) = {r['probabilidad_ataque']:.4f}")

        estilos.kpis([
            ("Etiqueta", r["etiqueta"].upper(), f"id {r['id']}"),
            ("Clase", r["clase"], f"p(clase) = {r['probabilidad_clase']:.4f}"),
            ("p(ataque)", f"{r['probabilidad_ataque']:.4f}", f"umbral {r['umbral']}"),
            ("Modelo", r["modelo"], f"versión {r['version_modelo']}"),
        ], alerta=(0,) if r["es_ataque"] else ())
        st.progress(min(1.0, float(r["probabilidad_ataque"])))

        if r.get("avisos"):
            for aviso in r["avisos"]:
                st.warning(aviso)

        if familias and eleccion != "manual":
            acierto = (r["clase"] == eleccion) if r["es_ataque"] else (eleccion == "normal")
            st.caption(
                "Coincide con la etiqueta real." if acierto
                else "No coincide con la etiqueta real de la fila."
            )


# --------------------------------------------------------------------------
# Archivo CSV
# --------------------------------------------------------------------------
def _archivo_csv() -> None:
    st.markdown(
        f"El CSV debe traer las **{len(client.COLUMNAS)} columnas** del NSL-KDD. Si "
        "además incluye `label` o `family`, el tablero compara la predicción con la "
        "verdad y reporta aciertos por familia."
    )
    archivo = st.file_uploader("Archivo CSV", type=["csv"], key="up_csv")
    if archivo is None:
        st.caption(
            "Prueba con `datasets/sample_etiquetado.csv` (150 filas, 30 por familia) "
            "o `datasets/sample_trafico.csv` (60 filas sin etiqueta)."
        )
        return

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(archivo.getbuffer())
        ruta = Path(tmp.name)
    try:
        filas, familias = client.leer_csv(ruta, max_filas=2_000)
    except ValueError as exc:
        st.error(str(exc))
        return
    finally:
        ruta.unlink(missing_ok=True)

    total = len(filas)
    con_verdad = sum(1 for f in familias if f)
    estilos.kpis([
        ("Filas válidas", f"{total:,}", "listas para enviar"),
        ("Con etiqueta real", f"{con_verdad:,}", "columna family" if con_verdad
         else "sin columna family"),
        ("Tamaño máximo", "2,000", "por carga, en lotes de 200"),
    ])

    if st.button(f"Predecir {total:,} filas", type="primary", key="btn_lote"):
        barra = st.progress(0.0, text="Enviando lotes...")
        try:
            resultados = client.predecir_lote(
                filas, progreso=lambda f: barra.progress(f, text=f"{f * 100:.0f} %")
            )
        except client.ApiError as exc:
            barra.empty()
            st.error(str(exc))
            return
        barra.empty()
        st.session_state["lote_df"] = _tabla_resultados(resultados, familias)
        st.session_state["lote_familias"] = familias
        datos.invalidar()
        st.success(f"{len(resultados):,} filas analizadas y registradas en el historial.")

    if "lote_df" not in st.session_state:
        return

    df = st.session_state["lote_df"]
    familias = st.session_state.get("lote_familias") or []
    ataques = int(df["es_ataque"].sum())
    estilos.kpis([
        ("Analizadas", f"{len(df):,}", "una fila por predicción"),
        ("Ataques", f"{ataques:,}", "es_ataque = verdadero", 1),
        ("Normales", f"{len(df) - ataques:,}", "sin hallazgos"),
        ("Proporción", f"{100 * ataques / max(1, len(df)):.1f} %", "del lote"),
    ], alerta=(1,))

    izquierda, derecha = st.columns([2, 3], gap="large")
    with izquierda:
        st.subheader("Por clase")
        st.bar_chart(df["clase"].value_counts(), height=220, color="#0f5c4a")
    with derecha:
        st.subheader("Detección real")
        if any(familias):
            tabla = _evaluacion(df, familias)
            st.dataframe(tabla, hide_index=True)
            estilos.bloque(
                "Cómo leerla.",
                "Un ataque detectado en la familia equivocada sigue siendo una "
                "detección (columna Detección) pero no una clasificación correcta "
                "(columna Familia). Las dos cifras se reportan por separado porque "
                "el sistema avisa aunque no nombre bien la familia.",
            )
        else:
            st.info("El archivo no trae columna family: no hay verdad contra la cual comparar.")

    st.subheader("Detalle")
    st.dataframe(df, hide_index=True, height=380)
    st.download_button(
        "Descargar resultados (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="resultados_lote.csv",
        mime="text/csv",
    )


def _tabla_resultados(resultados: list[dict], familias: list[str | None]) -> pd.DataFrame:
    df = pd.DataFrame([
        {
            "id": r["id"],
            "es_ataque": bool(r["es_ataque"]),
            "etiqueta": r["etiqueta"],
            "clase": r["clase"],
            "probabilidad_ataque": float(r["probabilidad_ataque"]),
            "probabilidad_clase": float(r["probabilidad_clase"]),
        }
        for r in resultados
    ])
    if any(familias):
        df["real"] = [f or "" for f in familias]
    return df


def _evaluacion(df: pd.DataFrame, familias: list[str | None]) -> pd.DataFrame:
    """Cuenta detección y clasificación correcta por familia verdadera."""
    datos_df = df.copy()
    datos_df["real"] = [f or "sin etiqueta" for f in familias]
    filas = []
    for familia, grupo in datos_df.groupby("real", sort=True):
        detectados = int(grupo["es_ataque"].sum())
        correctos = int((grupo["clase"] == familia).sum()) if familia != "normal" else int(
            (~grupo["es_ataque"]).sum()
        )
        filas.append({
            "familia real": familia,
            "filas": len(grupo),
            "detección": f"{detectados}/{len(grupo)}",
            "familia correcta": f"{correctos}/{len(grupo)}",
        })
    return pd.DataFrame(filas)
