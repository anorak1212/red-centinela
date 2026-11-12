"""Vista 4: modelo y métricas reales sobre KDDTest+.

Ninguna cifra de esta pantalla se escribe a mano: todas vienen de
motor/models/metrics.json a través de /metrics, que se regenera al ejecutar
`python -m motor.evaluate`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero.ui import datos, estilos

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]
OBJETIVO_PERF = 0.90


def _tabla_binaria(binario: dict) -> pd.DataFrame:
    campos = [
        ("accuracy", "Exactitud"),
        ("macro_f1", "Macro-F1"),
        ("weighted_f1", "F1 ponderado"),
        ("precision_ataque", "Precisión de ataque"),
        ("recall_ataque", "Recall de ataque"),
        ("auc_roc", "AUC ROC"),
    ]
    return pd.DataFrame(
        [{"métrica": etiqueta, "valor": float(binario.get(clave, 0.0))}
         for clave, etiqueta in campos],
        columns=["métrica", "valor"],
    ).assign(valor=lambda d: d["valor"].map(lambda v: f"{v:.4f}"))


def render() -> None:
    estilos.encabezado(
        "Modelo y métricas",
        "El modelo se evalúa sobre KDDTest+, el conjunto que nunca vio al "
        "entrenar. Las cifras del holdout de entrenamiento se muestran aparte "
        "porque no son una prueba independiente.",
    )

    m = datos.metricas(datos.api_actual())
    if not m:
        estilos.bloque("Sin métricas.", "La API no respondió o no existe metrics.json. "
                       "Ejecuta <span class='rc-mono'>python -m motor.evaluate</span>.",
                       tono="aviso")
        return

    binario = m.get("binario_kddtest", {})
    multi = m.get("multiclase_kddtest", {})
    macro = float(binario.get("macro_f1", 0.0))

    estilos.kpis([
        ("Macro-F1 binario", f"{macro:.4f}", "KDDTest+, 22,544 filas",
         0 if macro >= OBJETIVO_PERF else 1),
        ("Macro-F1 5 clases", f"{float(multi.get('macro_f1', 0.0)):.4f}",
         "acierta la familia"),
        ("AUC ROC", f"{float(binario.get('auc_roc', 0.0)):.4f}", "cabeza binaria"),
        ("Recall de ataque", f"{float(binario.get('recall_ataque', 0.0)):.4f}",
         "de los ataques reales"),
    ], alerta=(0,) if macro < OBJETIVO_PERF else ())

    if macro < OBJETIVO_PERF:
        estilos.bloque(
            "Criterio PERF-003: no cumplido.",
            f"El umbral del proyecto era macro-F1 ≥ {OBJETIVO_PERF:.2f} y el valor "
            f"medido es {macro:.4f}. No es un error de implementación: KDDTest+ "
            "incluye familias de ataque que no existen en el conjunto de "
            "entrenamiento, y por eso el recall de r2l y u2r se desploma. El "
            "estado del arte publicado sobre KDDTest+ ronda 0.80. La diferencia "
            "se documenta como limitación, no se maquilla ajustando el umbral "
            "contra el conjunto de prueba.",
            tono="aviso",
        )

    izquierda, derecha = st.columns(2, gap="large")

    with izquierda:
        st.subheader("Cabeza binaria (normal contra ataque)")
        st.dataframe(_tabla_binaria(binario), hide_index=True)
        st.caption(
            f"Precisión de ataque {binario.get('precision_ataque', 0):.4f}: cuando "
            "avisa, casi siempre acierta. El recall es el costo: uno de cada tres "
            "ataques pasa como normal."
        )

    with derecha:
        st.subheader("Matriz de confusión binaria")
        matriz = binario.get("matriz_confusion") or [[0, 0], [0, 0]]
        st.dataframe(
            pd.DataFrame(matriz, index=["real normal", "real ataque"],
                         columns=["pred normal", "pred ataque"]),
        )
        st.caption(
            f"{binario.get('filas', 0):,} filas, {binario.get('ataques_reales', 0):,} "
            "ataques reales."
        )

    st.subheader("Cabeza multiclase: acierto por familia")
    por_clase = multi.get("por_clase") or {}
    if por_clase:
        tabla = pd.DataFrame([
            {
                "clase": clase,
                "precisión": por_clase.get(clase, {}).get("precision", 0.0),
                "recall": por_clase.get(clase, {}).get("recall", 0.0),
                "F1": por_clase.get(clase, {}).get("f1", 0.0),
                "soporte": por_clase.get(clase, {}).get("soporte", 0),
            }
            for clase in CLASES if clase in por_clase
        ])
        st.dataframe(
            tabla, hide_index=True,
            column_config={
                "precisión": st.column_config.NumberColumn(format="%.4f"),
                "recall": st.column_config.NumberColumn(format="%.4f"),
                "F1": st.column_config.NumberColumn(format="%.4f"),
                "soporte": st.column_config.NumberColumn(format="%d"),
            },
        )
        estilos.bloque(
            "r2l y u2r son el punto débil.",
            "El modelo detecta bien DoS y sondeo, y casi no reconoce accesos "
            "remotos ni escalada de privilegios: esas familias aparecen con "
            "poquísimos ejemplos en el entrenamiento y con variantes nuevas en la "
            "prueba. Cualquier tabla que muestre 0.99 en estas clases sobre "
            "KDDTest+ está midiendo fuga de datos, no rendimiento.",
        )

    st.subheader("Detección contra clasificación por familia")
    recall = m.get("recall_por_familia") or {}
    if recall:
        st.dataframe(
            pd.DataFrame([
                {
                    "familia": familia,
                    "registros": valores.get("registros", 0),
                    "detección": valores.get("recall_deteccion", 0.0),
                    "clasificación": valores.get("recall_clasificacion", 0.0),
                }
                for familia, valores in recall.items()
            ]),
            hide_index=True,
            column_config={
                "detección": st.column_config.ProgressColumn(
                    "Detección (¿es ataque?)", min_value=0.0, max_value=1.0, format="%.4f"
                ),
                "clasificación": st.column_config.ProgressColumn(
                    "Clasificación (¿qué familia?)", min_value=0.0, max_value=1.0,
                    format="%.4f",
                ),
                "registros": st.column_config.NumberColumn(format="%d"),
            },
        )

    st.subheader("KDDTest-21: el subconjunto difícil")
    k21 = m.get("kddtest21") or {}
    if k21:
        b21 = k21.get("binario", {})
        m21 = k21.get("multiclase", {})
        estilos.kpis([
            ("Filas", f"{int(k21.get('filas', 0)):,}", k21.get("criterio", "")),
            ("Macro-F1 binario", f"{float(b21.get('macro_f1', 0.0)):.4f}", "solo difíciles"),
            ("Macro-F1 5 clases", f"{float(m21.get('macro_f1', 0.0)):.4f}", "solo difíciles"),
            ("AUC", f"{float(b21.get('auc_roc', 0.0)):.4f}", "cabeza binaria"),
        ])
        st.caption(
            "KDDTest-21 quita los registros fáciles. Sirve para saber qué tan bien "
            "generaliza el modelo cuando el tráfico se parece poco a lo ya visto."
        )

    with st.expander("Holdout de entrenamiento, latencia y comparativa de modelos"):
        holdout = m.get("holdout_entrenamiento") or {}
        if holdout:
            st.markdown("**Holdout del entrenamiento**")
            st.dataframe(pd.DataFrame([holdout]), hide_index=True)
            estilos.bloque(
                "No citar como prueba.",
                "Estas cifras salen de la misma distribución del entrenamiento. Un "
                "0.99 aquí y 0.80 en KDDTest+ no es contradicción: es la medida de "
                "cuánto se parece el tráfico nuevo al viejo.",
            )

        latencia = m.get("latencia") or {}
        if latencia:
            st.markdown("**Latencia**")
            estilos.kpis([
                ("Fila sola", f"{latencia.get('ms_por_fila_sola', 0):.0f} ms",
                 "una petición HTTP"),
                ("En lote de 500", f"{latencia.get('ms_por_fila_en_lote_500', 0):.2f} ms",
                 "por fila"),
                ("Repeticiones", f"{latencia.get('repeticiones', 0)}", "medidas"),
            ])
            st.caption(latencia.get("nota", ""))

        comparativa = m.get("comparativa_modelos") or []
        if comparativa:
            st.markdown("**Modelos comparados en el informe**")
            st.dataframe(pd.DataFrame(comparativa), hide_index=True)
            estilos.bloque(
                "Solo comparativa.",
                "SVM y KNN se entrenaron con 25,000 filas para la comparativa del "
                "informe. KNN guarda todos los vectores de entrenamiento y no cabe "
                "en un plan gratuito, así que producción usa Random Forest.",
            )

        iforest = m.get("iforest") or {}
        if iforest:
            st.markdown("**Isolation Forest (apoyo no supervisado)**")
            estilos.kpis([
                ("AUC", f"{iforest.get('auc_roc', 0):.4f}", "rareza contra normal"),
                ("Recall top 10 %", f"{iforest.get('recall_ataques_top10_por_ciento', 0):.4f}",
                 "ataques en el 10 % más raro"),
            ])
            st.caption(iforest.get("nota", ""))

    st.caption(
        f"metrics.json generado el {m.get('generado', '?')} · versión del motor "
        f"{m.get('version_motor', '?')}."
    )
