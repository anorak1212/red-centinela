"""Vista 4: modelo y métricas.

La vista que un jurado técnico va a interrogar. Regla de la casa: se publica lo
que el modelo mide sobre datos que no vio al entrenar, con el conjunto que se
usó escrito al lado. El holdout interno aparece marcado como lo que es, una
prueba sobre la misma distribución, no una validación independiente.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero.ui import datos, estilos, graficas

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]


def render() -> None:
    estilos.encabezado(
        "Modelo y métricas",
        "Random Forest de dos cabezas más Isolation Forest, evaluado sobre "
        "KDDTest+ (22,544 filas que no vio al entrenar) y sobre su subconjunto "
        "difícil KDDTest-21. Nada de estas cifras se ajustó contra el conjunto de prueba.",
    )

    metricas = datos.metricas(datos.api_actual())
    if not metricas:
        estilos.bloque(
            "La API no responde.",
            "Las métricas viven en la API (/metrics), que las lee de "
            "<span class='rc-mono'>motor/models/metrics.json</span>. "
            "Sin servicio no hay cifras que mostrar.",
            tono="aviso",
        )
        return

    binario = metricas.get("binario_kddtest") or {}
    multi = metricas.get("multiclase_kddtest") or {}
    dificil = (metricas.get("kddtest21") or {})
    dificil_bin = dificil.get("binario") or {}
    familias = metricas.get("recall_por_familia") or {}
    iforest = metricas.get("iforest") or {}
    holdout = metricas.get("holdout_entrenamiento") or {}
    latencia = metricas.get("latencia") or {}
    tiempos = metricas.get("tiempos_entrenamiento_segundos") or {}
    produccion = metricas.get("modelo_produccion") or {}

    estilos.banda(
        "Rendimiento medido, sin maquillaje",
        "Generado el "
        f"{str(metricas.get('generado', '?'))[:10]} con la versión "
        f"{metricas.get('version_motor', '?')} del motor. "
        "El umbral de decisión es 0.41 y se calibró sobre un holdout interno, nunca sobre KDDTest+.",
        [
            (f"{float(binario.get('macro_f1', 0)):.4f}", "Macro-F1 binario", "KDDTest+, meta 0.90"),
            (f"{float(binario.get('weighted_f1', 0)):.4f}", "F1 ponderado", "KDDTest+"),
            (f"{float(binario.get('auc_roc', 0)):.4f}", "AUC ROC", "capacidad de separación"),
            (f"{float(multi.get('macro_f1', 0)):.4f}", "Macro-F1 5 clases", "la cabeza difícil"),
            (f"{float(dificil_bin.get('macro_f1', 0)):.4f}", "Macro-F1 KDDTest-21", "subconjunto duro"),
        ],
    )

    _seccion_binaria(binario, dificil_bin)
    _seccion_multiclase(multi)
    _seccion_familias(familias, multi)
    _seccion_dificil(binario, dificil, dificil_bin)
    _seccion_comparativa(metricas.get("comparativa_modelos") or [])
    _seccion_honestidad(holdout, iforest)
    _seccion_costo(latencia, tiempos, produccion)


# --------------------------------------------------------------------------
def _seccion_binaria(binario_test: dict, dificil_bin: dict) -> None:
    conjuntos = {"KDDTest+": binario_test}
    if dificil_bin.get("matriz_confusion"):
        conjuntos["KDDTest-21"] = dificil_bin
    cab_izq, cab_der = st.columns([3, 2], vertical_alignment="bottom")
    nombre = cab_der.segmented_control(
        "Conjunto evaluado", list(conjuntos), default="KDDTest+", key="conjunto_binario",
        help="Las mismas cifras sobre el conjunto completo o sobre su subconjunto difícil.",
    ) or "KDDTest+"
    binario = conjuntos[nombre]
    with cab_izq:
        estilos.seccion("1", "Cabeza binaria: normal contra ataque",
                        f"{int(binario.get('filas', 0)):,} filas de {nombre}")
    estilos.kpis([
        ("Macro-F1", f"{float(binario.get('macro_f1', 0)):.4f}", "media de las dos clases", True),
        ("Exactitud", f"{float(binario.get('accuracy', 0)):.4f}", "aciertos totales"),
        ("Precisión de ataque", f"{float(binario.get('precision_ataque', 0)):.4f}",
         "de lo marcado como ataque, cuánto lo era"),
        ("Recall de ataque", f"{float(binario.get('recall_ataque', 0)):.4f}",
         "de los ataques reales, cuántos se vieron"),
        ("AUC ROC", f"{float(binario.get('auc_roc', 0)):.4f}", "independiente del umbral"),
        ("Ataques reales", f"{int(binario.get('ataques_reales', 0)):,}",
         "en el conjunto de prueba"),
    ])

    izquierda, derecha = st.columns([2, 3], gap="large")
    matriz = binario.get("matriz_confusion") or [[0, 0], [0, 0]]
    with izquierda:
        st.altair_chart(
            graficas.matriz_confusion(matriz, ["normal", "ataque"]),
            width="stretch",
        )
    with derecha:
        vn, fp = int(matriz[0][0]), int(matriz[0][1])
        fn, vp = int(matriz[1][0]), int(matriz[1][1])
        precision = vp / max(1, vp + fp)
        recall = vp / max(1, vp + fn)
        estilos.tabla(
            [
                {"Métrica": "Verdaderos negativos", "Filas": f"{vn:,}",
                 "Lectura": "tráfico normal que pasó sin alerta"},
                {"Métrica": "Falsos positivos", "Filas": f"{fp:,}",
                 "Lectura": f"{100 * fp / max(1, vn + fp):.2f} % del tráfico normal marcado como ataque"},
                {"Métrica": "Falsos negativos", "Filas": f"{fn:,}",
                 "Lectura": "ataques que pasaron sin alerta: el error caro"},
                {"Métrica": "Verdaderos positivos", "Filas": f"{vp:,}",
                 "Lectura": "ataques detectados y avisados"},
                {"Métrica": "Precisión y recall", "Filas": f"{precision:.4f} y {recall:.4f}",
                 "Lectura": "precisión alta, recall moderado: el modelo calla antes que gritar"},
            ],
            ["Métrica", "Filas", "Lectura"],
            numericas=("Filas",), fuertes=("Métrica",),
        )
    estilos.fuente(
        "La matriz y las seis cifras salen de motor/models/metrics.json, calculadas "
        "una sola vez sobre KDDTest+ y publicadas sin cambios por /metrics."
    )


def _seccion_multiclase(multi: dict) -> None:
    por_clase = multi.get("por_clase") or {}
    estilos.seccion("2", "Cinco clases: qué familia es el ataque",
                    f"macro-F1 {float(multi.get('macro_f1', 0)):.4f}")
    if not por_clase:
        st.info("Sin métricas multiclase.")
        return

    filas = []
    for clase in CLASES:
        fila = por_clase.get(clase) or {}
        filas.append({
            "Clase": clase,
            "Precisión": f"{float(fila.get('precision', 0)):.4f}",
            "Recall": f"{float(fila.get('recall', 0)):.4f}",
            "F1": f"{float(fila.get('f1', 0)):.4f}",
            "Soporte": f"{int(fila.get('soporte', 0)):,}",
        })
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        estilos.tabla(filas, ["Clase", "Precisión", "Recall", "F1", "Soporte"],
                      numericas=("Precisión", "Recall", "F1", "Soporte"), fuertes=("Clase",))
        estilos.fuente(
            "Soporte es el número de filas reales de cada clase en KDDTest+. "
            "U2R tiene 67: un solo acierto mueve su recall casi dos puntos."
        )
    with derecha:
        estilos.barras(
            [(c, float((por_clase.get(c) or {}).get("f1", 0)),
              f"F1 {float((por_clase.get(c) or {}).get('f1', 0)):.3f}",
              "ok" if float((por_clase.get(c) or {}).get("f1", 0)) >= 0.7 else "mal")
             for c in CLASES],
            escala=1.0,
        )
        st.caption("F1 por clase. R2L y U2R son el techo real de este modelo: "
                   "no se detectan como familia porque se parecen demasiado al tráfico normal.")

    matriz = multi.get("matriz_confusion") or []
    if matriz:
        st.altair_chart(graficas.matriz_confusion(matriz, CLASES), width="stretch")
        estilos.fuente(
            "Matriz de confusión de las cinco clases: la fila es la familia real y la "
            "columna lo que el modelo dijo. La columna 'normal' concentra los errores."
        )


def _seccion_familias(familias: dict, multi: dict) -> None:
    if not familias:
        return
    estilos.seccion("3", "Detección contra clasificación",
                    "dos preguntas distintas, dos cifras distintas")
    largo = []
    for clase in CLASES:
        if clase == "normal":
            continue
        fila = familias.get(clase) or {}
        largo.append({"familia": clase, "serie": "Detección",
                      "recall": float(fila.get("recall_deteccion", 0))})
        largo.append({"familia": clase, "serie": "Clasificación",
                      "recall": float(fila.get("recall_clasificacion", 0))})
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        st.altair_chart(graficas.valores_por_categoria(pd.DataFrame(largo)),
                        width="stretch")
        estilos.fuente(
            "Detección: el sistema dijo 'ataque', sin importar la familia. "
            "Clasificación: además acertó la familia. Al negocio le sirve la primera, y "
            "la segunda es la que un sinodal va a preguntar."
        )
    with derecha:
        estilos.kpis([
            ("DoS", f"{float((familias.get('dos') or {}).get('recall_deteccion', 0)):.3f}",
             "recall de detección"),
            ("Probe", f"{float((familias.get('probe') or {}).get('recall_deteccion', 0)):.3f}",
             "recall de detección"),
            ("R2L", f"{float((familias.get('r2l') or {}).get('recall_deteccion', 0)):.3f}",
             "acceso remoto, el punto débil", True),
            ("U2R", f"{float((familias.get('u2r') or {}).get('recall_deteccion', 0)):.3f}",
             "escalada de privilegios", True),
        ])
        estilos.bloque(
            "Por qué R2L falla.",
            "En KDDTest+, R2L incluye familias de ataque que no existen en "
            "KDDTrain+: el modelo no las puede nombrar porque nunca las vio. "
            "El recall de detección (0.0915) es lo que el sistema hace hoy, mientras que "
            "el de clasificación (0.0035) mide la etiqueta, no la alerta.",
        )


def _seccion_dificil(binario: dict, dificil: dict, dificil_bin: dict) -> None:
    estilos.seccion("4", "KDDTest-21: el subconjunto difícil",
                    dificil.get("criterio", ""))
    estilos.kpis([
        ("Macro-F1 binario", f"{float(dificil_bin.get('macro_f1', 0)):.4f}",
         f"{int(dificil.get('filas', 0)):,} filas", True),
        ("Exactitud", f"{float(dificil_bin.get('accuracy', 0)):.4f}", "sobre el subconjunto"),
        ("Recall de ataque", f"{float(dificil_bin.get('recall_ataque', 0)):.4f}",
         "cae respecto a KDDTest+"),
        ("AUC ROC", f"{float(dificil_bin.get('auc_roc', 0)):.4f}", "sigue separando"),
    ])
    estilos.tabla(
        [
            {"Conjunto": "KDDTest+", "Filas": f"{int(binario.get('filas', 0)):,}",
             "Macro-F1": f"{float(binario.get('macro_f1', 0)):.4f}",
             "Recall de ataque": f"{float(binario.get('recall_ataque', 0)):.4f}"},
            {"Conjunto": "KDDTest-21", "Filas": f"{int(dificil.get('filas', 0)):,}",
             "Macro-F1": f"{float(dificil_bin.get('macro_f1', 0)):.4f}",
             "Recall de ataque": f"{float(dificil_bin.get('recall_ataque', 0)):.4f}"},
        ],
        ["Conjunto", "Filas", "Macro-F1", "Recall de ataque"],
        numericas=("Filas", "Macro-F1", "Recall de ataque"), fuertes=("Conjunto",),
    )
    estilos.fuente(
        "KDDTest-21 quita las filas más fáciles de KDDTest+. Si las cifras no bajan "
        "al pasar a este subconjunto, algo está filtrando información: aquí bajan, y eso "
        "es la señal de que la evaluación es honesta."
    )


def _seccion_comparativa(comparativa: list[dict]) -> None:
    if not comparativa:
        return
    estilos.seccion("5", "Comparativa de modelos", "solo comparativa, no se despliega")
    otros = [dict(m) for m in comparativa]
    filas = []
    for modelo in otros:
        nombre = modelo["modelo"]
        f1 = modelo.get("macro_f1_binario")
        filas.append({
            "Modelo": nombre,
            "Filas": f"{int(modelo.get('filas_entrenamiento', 0)):,}",
            "Macro-F1": "ver sección 1" if f1 is None else f"{float(f1):.4f}",
            "Entrenamiento (s)": f"{float(modelo.get('segundos_entrenamiento', 0)):.1f}",
            "Nota": estilos.organico(modelo.get("nota", "")),
        })
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        estilos.tabla(filas, ["Modelo", "Filas", "Macro-F1", "Entrenamiento (s)", "Nota"],
                      numericas=("Filas", "Macro-F1", "Entrenamiento (s)"), fuertes=("Modelo",))
    with derecha:
        grafica = pd.DataFrame([
            {"modelo": m["modelo"], "macro_f1_binario": float(m.get("macro_f1_binario") or 0),
             "filas_entrenamiento": int(m.get("filas_entrenamiento", 0)),
             "nota": estilos.organico(m.get("nota", ""))}
            for m in otros
        ])
        if not grafica.empty:
            st.altair_chart(graficas.comparativa(grafica), width="stretch")
            estilos.fuente("SVC y KNN se entrenaron con 25,000 filas (una submuestra) "
                           "para que el experimento cupiera en la sesión de Colab.")
    estilos.bloque(
        "Cuidado al leer esta tabla.",
        "El macro-F1 de SVC y KNN no es comparable con el de producción: se entrenaron "
        "con una submuestra de 25,000 filas y se midieron sobre otra partición. "
        "La comparativa sirve para justificar la elección (KNN es caro en memoria: 60 MB "
        "y una predicción de ~250 ms con 125,973 filas), no para declarar un ganador.",
        tono="aviso",
    )


def _seccion_honestidad(holdout: dict, iforest: dict) -> None:
    estilos.seccion("6", "Holdout interno e Isolation Forest",
                    "por qué el 0.9992 no es el resultado del proyecto")
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        st.subheader("Holdout interno")
        estilos.kpis([
            ("Macro-F1 binario", f"{float(holdout.get('macro_f1_binario', 0)):.4f}",
             "misma distribución del entrenamiento"),
            ("Macro-F1 5 clases", f"{float(holdout.get('macro_f1_multiclase', 0)):.4f}",
             "misma distribución"),
        ])
        estilos.bloque(
            "Estas cifras no cumplen PERF-003.",
            "El holdout sale de la misma distribución que KDDTrain+, así que mide "
            "memorización de la distribución, no generalización a ataques nuevos. "
            "Se publica por transparencia y se marca para que nadie la cite como logro.",
            tono="aviso",
        )
    with derecha:
        st.subheader("Isolation Forest (no supervisado)")
        estilos.kpis([
            ("AUC ROC", f"{float(iforest.get('auc_roc', 0)):.4f}",
             "entrenado solo con tráfico normal"),
            ("Recall en el 10 % más anómalo",
             f"{100 * float(iforest.get('recall_ataques_top10_por_ciento', 0)):.2f} %",
             "de los ataques caen en ese décimo"),
        ])
        st.caption(estilos.organico(iforest.get("nota", "")))


def _seccion_costo(latencia: dict, tiempos: dict, produccion: dict) -> None:
    estilos.seccion("7", "Costo computacional y artefactos", "medido en la máquina de desarrollo")
    estilos.kpis([
        ("Latencia por fila", f"{float(latencia.get('ms_por_fila_sola', 0)):.0f} ms",
         f"{int(latencia.get('repeticiones', 0))} repeticiones"),
        ("En lote de 500", f"{float(latencia.get('ms_por_fila_en_lote_500', 0)):.3f} ms",
         "por fila, con el modelo caliente"),
        ("Entrenar RF binario", f"{float(tiempos.get('rf_binario', 0)):.1f} s", "KDDTrain+ completo"),
        ("Entrenar RF multiclase", f"{float(tiempos.get('rf_multiclase', 0)):.1f} s", ""),
        ("Entrenar Isolation Forest", f"{float(tiempos.get('iforest', 0)):.1f} s", ""),
    ])
    st.caption(
        f"Modelo en producción: {produccion.get('nombre', '?')} con las cabezas "
        f"{', '.join(produccion.get('cabezas') or [])}, umbral "
        f"{produccion.get('umbral_decision', '?')}. "
        + estilos.organico(latencia.get("nota", ""))
    )
