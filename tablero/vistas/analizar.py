"""Vista 2: analizar una conexión o un archivo completo."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from tablero import auth, client
from tablero.ui import datos, estilos, graficas, preferencias

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

    degradado = estilos.aviso_degradado(
        estado, "Los controles de predicción quedan deshabilitados hasta entonces."
    )
    if not auth.puede_escribir(st.session_state):
        estilos.sin_permiso("predecir (cada análisis se guarda en el historial)")
        degradado = True

    individual, lote = st.tabs([":material/cable: Conexión individual",
                                ":material/upload_file: Archivo CSV"])
    with individual:
        _conexion_individual(degradado)
    with lote:
        _archivo_csv(degradado)


# --------------------------------------------------------------------------
# Conexión individual
# --------------------------------------------------------------------------
PROTOCOLOS = ["tcp", "udp", "icmp"]
FLAGS = ["sf", "s0", "rej", "rsto", "rstr", "rstos0", "sh", "s1", "s2", "s3", "oth"]
# Campos que más pesan para distinguir familias en el NSL-KDD. El resto de las
# 41 columnas se toma de la fila de partida y se puede editar en modo JSON.
CAMPOS_GUIADOS = [
    ("duration", "Duración (s)", 1.0),
    ("src_bytes", "Bytes origen → destino", 1.0),
    ("dst_bytes", "Bytes destino → origen", 1.0),
    ("count", "Conexiones al mismo host (2 s)", 1.0),
    ("srv_count", "Conexiones al mismo servicio (2 s)", 1.0),
    ("serror_rate", "Tasa de errores SYN", 0.01),
    ("same_srv_rate", "Tasa mismo servicio", 0.01),
    ("dst_host_count", "Conexiones al host destino", 1.0),
]


def _conexion_individual(degradado: bool) -> None:
    ejemplos = client.ejemplos_etiquetados(MUESTRA)
    familias = [f for f in ("normal", "dos", "probe", "r2l", "u2r") if f in ejemplos]

    cab1, cab2 = st.columns([2, 3], gap="large")
    if familias:
        eleccion = cab1.selectbox(
            "Fila de partida",
            familias,
            help="Cada opción es una conexión real de KDDTest+ con su familia "
                 "verdadera. Se puede modificar antes de predecir.",
        )
        base = dict(ejemplos[eleccion])
    else:
        eleccion = "manual"
        base = {c: (0.0 if c not in client.CATEGORICAS else "") for c in client.COLUMNAS}
        cab1.warning(
            "No se encontró datasets/sample_etiquetado.csv: escribe las 41 "
            "características a mano."
        )
    modo = cab2.segmented_control(
        "Modo de edición", ["Formulario guiado", "JSON completo"],
        default="Formulario guiado", key=f"modo_{eleccion}",
        help="El formulario cambia los campos clave y el JSON permite tocar las 41 columnas.",
    ) or "Formulario guiado"

    texto = ""
    if modo == "Formulario guiado":
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            proto = str(base.get("protocol_type") or "tcp")
            flag = str(base.get("flag") or "sf")
            base["protocol_type"] = c1.selectbox(
                "Protocolo", PROTOCOLOS,
                index=PROTOCOLOS.index(proto) if proto in PROTOCOLOS else 0,
                key=f"g_proto_{eleccion}")
            base["service"] = c2.text_input(
                "Servicio", value=str(base.get("service") or "http"),
                key=f"g_serv_{eleccion}").strip().lower()
            opciones_flag = FLAGS if flag in FLAGS else [flag, *FLAGS]
            base["flag"] = c3.selectbox("Flag", opciones_flag,
                                        index=opciones_flag.index(flag),
                                        key=f"g_flag_{eleccion}")
            columnas = st.columns(4)
            for i, (campo, etiqueta, paso) in enumerate(CAMPOS_GUIADOS):
                es_tasa = paso < 1
                base[campo] = columnas[i % 4].number_input(
                    etiqueta, min_value=0.0, max_value=1.0 if es_tasa else None,
                    value=float(base.get(campo) or 0.0), step=paso,
                    format="%.2f" if es_tasa else "%.0f", key=f"g_{campo}_{eleccion}",
                )
            st.caption("Las otras 33 características se envían tal como vienen en la fila de partida.")
    else:
        texto = st.text_area(
            "Características enviadas (41 columnas, JSON editable)",
            value=json.dumps(base, indent=2, ensure_ascii=False),
            height=320, key=f"json_{eleccion}",
        )

    col1, col2 = st.columns([1, 3], vertical_alignment="center")
    predecir = col1.button("Predecir", type="primary", key="btn_predecir_uno",
                           icon=":material/bolt:", disabled=degradado, width="stretch")
    if familias:
        col2.caption(
            f"Etiqueta real de esta fila: **{eleccion}**. Útil para mostrar en la "
            "demo si el modelo acierta o confunde la familia."
        )

    if predecir:
        if modo == "JSON completo":
            try:
                features = json.loads(texto)
            except json.JSONDecodeError as exc:
                st.error(f"El JSON no es válido: {exc.msg} (línea {exc.lineno}).")
                return
        else:
            features = base
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
            estilos.banda(
                tono="ataque", eyebrow="Resultado de /predict",
                titulo=f"Ataque de la familia {r['clase'].upper()}",
                subtitulo="El registro superó el umbral de decisión y quedó en el historial. "
                "Si el bot está configurado, la alerta se envía por Telegram.",
                cifras=[
                    (f"{r['probabilidad_ataque']:.4f}", "p(ataque)", "probabilidad de la cabeza binaria"),
                    (r["clase"], "Clase", f"confianza {r['probabilidad_clase']:.4f}"),
                    (str(r["umbral"]), "Umbral", "punto de corte calibrado"),
                    (str(r["id"]), "ID", "registro en el historial"),
                ],
            )
        else:
            estilos.banda(
                tono="sano", eyebrow="Resultado de /predict",
                titulo="Tráfico normal",
                subtitulo="El registro no superó el umbral de decisión. Queda en el historial "
                "para que el conteo de tráfico analizado sea real, no una muestra.",
                cifras=[
                    (f"{r['probabilidad_ataque']:.4f}", "p(ataque)", "por debajo del umbral"),
                    (r["clase"], "Clase", f"confianza {r['probabilidad_clase']:.4f}"),
                    (str(r["umbral"]), "Umbral", "punto de corte calibrado"),
                    (str(r["id"]), "ID", "registro en el historial"),
                ],
            )

        estilos.progress_probabilidad(r["probabilidad_ataque"], float(r["umbral"]))

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
def _archivo_csv(degradado: bool) -> None:
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        st.markdown(
            f"El CSV debe traer las **{len(client.COLUMNAS)} columnas** del NSL-KDD. Si "
            "además incluye `label` o `family`, el tablero compara la predicción con la "
            "verdad y reporta aciertos por familia."
        )
        archivo = st.file_uploader("Archivo CSV", type=["csv"], key="up_csv")
    with derecha:
        st.markdown("**¿No tienes un archivo?**")
        st.download_button(
            "Plantilla vacía (41 columnas)", client.plantilla_csv().encode("utf-8"),
            file_name="plantilla_red_centinela.csv", mime="text/csv",
            icon=":material/download:", width="stretch", key="dl_plantilla",
        )
        if MUESTRA.exists():
            st.download_button(
                "Muestra etiquetada (150 filas)", MUESTRA.read_bytes(),
                file_name=MUESTRA.name, mime="text/csv",
                icon=":material/dataset:", width="stretch", key="dl_muestra",
            )
        st.caption("La muestra trae 30 filas reales de KDDTest+ por familia, con columna family.")
    if archivo is None:
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
        ("Tamaño máximo", "2,000",
         f"por carga, en lotes de {int(preferencias.obtener('tamano_lote'))}"),
    ])

    if st.button(f"Predecir {total:,} filas", type="primary", key="btn_lote",
                 icon=":material/bolt:", disabled=degradado):
        barra = st.progress(0.0, text="Enviando lotes...")
        try:
            resultados = client.predecir_lote(
                filas, tamano=int(preferencias.obtener("tamano_lote")),
                progreso=lambda f: barra.progress(f, text=f"{f * 100:.0f} %"),
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

    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        conteo = (
            df.groupby("clase", observed=True).size().reset_index(name="registros")
            .sort_values("registros", ascending=False)
        )
        st.altair_chart(
            graficas.barras_horizontales(conteo, "clase", "registros", "Filas del lote"),
            width="stretch",
        )
        estilos.fuente("Distribución del lote tal como lo clasificó el modelo.")
    with derecha:
        st.subheader("Detección real")
        if any(familias):
            tabla = _evaluacion(df, familias)
            estilos.tabla(tabla.to_dict("records"), list(tabla.columns),
                          numericas=("filas",), fuertes=("familia real",))
            estilos.bloque(
                "Cómo leerla.",
                "Un ataque detectado en la familia equivocada sigue siendo una "
                "detección (columna Detección) pero no una clasificación correcta "
                "(columna Familia). Las dos cifras se reportan por separado porque "
                "el sistema avisa aunque no nombre bien la familia.",
            )
        else:
            st.info("El archivo no trae columna family: no hay verdad contra la cual comparar.")

    if any(familias):
        st.subheader("Matriz de confusión del lote")
        orden = ["normal", "dos", "probe", "r2l", "u2r"]
        reales = [f or "" for f in familias]
        predichas = ["normal" if not a else c for a, c in zip(df["es_ataque"], df["clase"], strict=True)]
        matriz = [[sum(1 for r, p in zip(reales, predichas, strict=True) if r == fila and p == col)
                   for col in orden] for fila in orden]
        st.altair_chart(graficas.matriz_confusion(matriz, orden), width="stretch")
        estilos.fuente("Cada fila es la familia real del archivo y cada columna, la decisión de la API "
                       "(normal si no superó el umbral, la clase predicha si sí).")

    cab1, cab2 = st.columns([3, 1], vertical_alignment="bottom")
    cab1.subheader("Detalle")
    solo_ataques = cab2.toggle("Solo ataques", key="lote_solo_ataques")
    detalle = df[df["es_ataque"]] if solo_ataques else df
    st.dataframe(
        detalle, hide_index=True, height=380,
        column_config={
            "probabilidad_ataque": st.column_config.ProgressColumn(
                "p(ataque)", min_value=0.0, max_value=1.0, format="%.3f"),
            "probabilidad_clase": st.column_config.NumberColumn("p(clase)", format="%.3f"),
        },
    )
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
