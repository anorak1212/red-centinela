"""Vista 1: resumen operativo del servicio.

Lo que un sinodal mira primero: cuánto tráfico pasó, cuánto fue ataque, qué
familias aparecieron y si el servicio está sano. Todo sale de la API; si la API
no responde, la vista lo dice en vez de dibujar ceros.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero import auth, client
from tablero.ui import datos, estilos, graficas, preferencias

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]
NOMBRE_CLASE = {
    "normal": "Normal",
    "dos": "DoS (denegación de servicio)",
    "probe": "Probe (sondeo)",
    "r2l": "R2L (acceso remoto)",
    "u2r": "U2R (escalada de privilegios)",
}


def render() -> None:
    api = datos.api_actual()
    estado = datos.salud(api)

    if estado is None:
        estilos.encabezado(
            "Resumen operativo",
            "Estado del servicio, volumen de tráfico analizado y alertas. "
            "Las cifras salen de la API, no de este navegador.",
        )
        estilos.estado_servicio(None)
        estilos.bloque(
            "La API no responde.",
            f"No hubo respuesta en <span class='rc-mono'>{api}</span>. Si es un "
            "servicio gratuito, probablemente está dormido: usa el botón "
            "<strong>Despertar servicio</strong> de la barra lateral. En local, "
            "arráncala con <span class='rc-mono'>python -m cli serve</span>.",
            tono="aviso",
        )
        return

    resumen = datos.resumen(api) or {}
    total = int(resumen.get("total", 0))
    ataques = int(resumen.get("ataques", 0))
    proporcion = (100.0 * ataques / total) if total else 0.0
    por_clase = resumen.get("por_clase") or {}
    sin_familia = int(resumen.get("sin_familia", 0) or 0)
    con_familia = int(resumen.get("con_familia", max(0, ataques - sin_familia)) or 0)
    familias = [c for c in CLASES if c != "normal" and int(por_clase.get(c, 0)) > 0]
    metricas = datos.metricas(api) or {}
    binario = metricas.get("binario_kddtest") or {}
    macro_f1 = binario.get("macro_f1")

    sano = estado.get("status") == "ok"
    estilos.banda(
        "Resumen operativo",
        "Servicio, tráfico analizado y alertas en una sola lectura. "
        "Cada cifra viene de /history/resumen y /metrics, no de esta sesión.",
        [
            (f"{total:,}", "Predicciones", "historial persistido de la API"),
            (f"{ataques:,}", "Ataques",
             (f"es_ataque = verdadero; {con_familia:,} con familia y "
              f"{sin_familia:,} sin familia clasificada")),
            (f"{proporcion:.1f} %", "Tasa de ataque", "sobre el total registrado"),
            (f"{len(familias)}/4", "Familias detectadas", "de las cuatro de ataque"),
            (f"{float(macro_f1):.3f}" if macro_f1 is not None else "sin datos",
             "Macro-F1", "KDDTest+, meta 0.90"),
        ],
        tono="sano" if sano else "",
        vivo=True,
    )
    estilos.aviso_degradado(estado, "Mientras tanto, esta vista muestra el historial ya guardado.")
    _panorama(metricas)
    _reporte(api, estado, metricas, resumen)

    # ------------------------------------------------------------------
    estilos.seccion("2", "Estado del servicio", "verificado contra /health")
    estilos.estado_servicio(estado)
    almacen = estado.get("almacen") or {}
    estilos.kpis([
        ("Umbral de decisión", str(estado.get("umbral_decision") or "sin datos"),
         "calibrado sobre holdout interno"),
        ("Artefactos", "íntegros" if estado.get("integridad_artefactos") else "no verificados",
         "cinco .joblib contra el manifiesto SHA-256",
         not estado.get("integridad_artefactos")),
        ("Modelos cargados", ", ".join(estado.get("modelo") or []) or "ninguno",
         f"versión {estado.get('version_modelo') or 'sin datos'}",
         not estado.get("modelos_disponibles", True)),
        ("Almacén", str(almacen.get("motor", "?")),
         "persistente" if almacen.get("persistente") else estilos.organico(almacen.get("nota") or "no persiste")),
    ])

    # ------------------------------------------------------------------
    estilos.seccion("3", "Dependencias del servicio", "alertas, artefactos y criterio de rendimiento")
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _bloque_alertas(api)
    with derecha:
        _bloque_integridad(api, estado)
        _bloque_rendimiento(macro_f1, binario)

    # ------------------------------------------------------------------
    cab_izq, cab_der = st.columns([3, 1], vertical_alignment="bottom")
    with cab_izq:
        estilos.seccion("4", "Actividad registrada", "últimas 500 predicciones")
    intervalo = int(preferencias.obtener("intervalo_auto"))
    auto = cab_der.toggle(
        f"Actualizar cada {intervalo} s", key="resumen_auto",
        help=f"Vuelve a leer /history cada {intervalo} s sin recargar la página. "
             "El intervalo se cambia en Configuración.",
    )

    def _actividad() -> None:
        _render_actividad(api)

    st.fragment(run_every=intervalo if auto else None)(_actividad)()


def _panorama(metricas: dict) -> None:
    """Gráficas del modelo que no dependen del historial.

    Salen de /metrics, que la API publica aunque no tenga los modelos cargados,
    así que la portada nunca queda vacía y nunca muestra datos inventados.
    """
    estilos.seccion("1", "Panorama del modelo", "KDDTest+, 22,544 filas que no vio al entrenar")
    binario = metricas.get("binario_kddtest") or {}
    if not binario:
        estilos.vacio("La API no publicó métricas",
                      "Falta <span class='rc-mono'>motor/models/metrics.json</span> en el servicio.")
        return
    multi = metricas.get("multiclase_kddtest") or {}
    familias = metricas.get("recall_por_familia") or {}
    holdout = metricas.get("holdout_entrenamiento") or {}
    dificil = (metricas.get("kddtest21") or {}).get("binario") or {}

    columnas = st.columns(4, gap="medium")
    medidores = [
        ("Macro-F1 binario", binario.get("macro_f1"), 0.90),
        ("Precisión de ataque", binario.get("precision_ataque"), None),
        ("Recall de ataque", binario.get("recall_ataque"), None),
        ("AUC ROC", binario.get("auc_roc"), None),
    ]
    for col, (titulo, valor, meta) in zip(columnas, medidores, strict=True):
        with col, st.container(border=True):
            estilos.panel_titulo(titulo)
            if valor is None:
                st.caption("sin datos")
            else:
                st.altair_chart(graficas.medidor(float(valor), titulo, meta), width="stretch")
    estilos.fuente("Macro-F1 es el criterio PERF-003 (meta 0.90, no cumplida). Las otras tres "
                   "no tienen meta fijada en el proyecto.")
    _indicadores(metricas)

    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        st.markdown("**Embudo de detección**")
        reales = int(binario.get("ataques_reales", 0))
        matriz = binario.get("matriz_confusion") or [[0, 0], [0, 0]]
        detectados = int(matriz[1][1]) if len(matriz) > 1 else 0
        mm = multi.get("matriz_confusion") or []
        familia_ok = sum(int(mm[i][i]) for i in range(1, len(mm))) if mm else 0
        etapas = pd.DataFrame([
            ("Ataques reales", reales),
            ("Detectados como ataque", detectados),
            ("Con la familia correcta", familia_ok),
        ], columns=["etapa", "filas"])
        etapas["pct"] = etapas["filas"] / max(1, reales)
        etapas["rotulo"] = [f"{f:,} ({p:.0%})" for f, p in zip(etapas["filas"], etapas["pct"],
                                                                 strict=True)]
        st.altair_chart(graficas.embudo(etapas), width="stretch")
        estilos.fuente("Los detectados salen de la cabeza binaria y la familia correcta, de la diagonal de la "
                       "matriz de cinco clases (filas de ataque).")
    with derecha:
        st.markdown("**F1 por clase**")
        por_clase = multi.get("por_clase") or {}
        if por_clase:
            st.altair_chart(graficas.f1_clases(pd.DataFrame([
                {"clase": c, "f1": float((por_clase.get(c) or {}).get("f1", 0)),
                 "soporte": int((por_clase.get(c) or {}).get("soporte", 0))}
                for c in CLASES
            ])), width="stretch")
            estilos.fuente("Línea ámbar: 0.90. R2L y U2R casi no se nombran bien.")

    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        st.markdown("**Detección contra clasificación por familia**")
        if familias:
            largo = []
            for c in CLASES[1:]:
                fila = familias.get(c) or {}
                largo.append({"familia": c, "serie": "Detección",
                              "recall": float(fila.get("recall_deteccion", 0))})
                largo.append({"familia": c, "serie": "Clasificación",
                              "recall": float(fila.get("recall_clasificacion", 0))})
            st.altair_chart(graficas.valores_por_categoria(pd.DataFrame(largo)), width="stretch")
            estilos.fuente("Detección: dijo 'ataque'. Clasificación: además acertó la familia.")
    with derecha:
        st.markdown("**Generalización**")
        filas = []
        if holdout.get("macro_f1_binario") is not None:
            filas.append(("Holdout", float(holdout["macro_f1_binario"]), "misma distribución"))
        filas.append(("KDDTest+", float(binario.get("macro_f1", 0)), "prueba honesta"))
        if dificil.get("macro_f1") is not None:
            filas.append(("KDDTest-21", float(dificil["macro_f1"]), "subconjunto difícil"))
        st.altair_chart(graficas.generalizacion(
            pd.DataFrame(filas, columns=["conjunto", "macro_f1", "nota"])), width="stretch")
        estilos.fuente("Que la cifra baje de izquierda a derecha es la señal de que no hay fuga "
                       "de datos. El holdout no cuenta para PERF-003.")


def _indicadores(metricas: dict) -> None:
    """Ocho indicadores derivados de /metrics, cada uno con su fórmula en la nota."""
    binario = metricas.get("binario_kddtest") or {}
    multi = metricas.get("multiclase_kddtest") or {}
    iforest = metricas.get("iforest") or {}
    latencia = metricas.get("latencia") or {}
    m = binario.get("matriz_confusion") or [[0, 0], [0, 0]]
    vn, fp, fn, vp = int(m[0][0]), int(m[0][1]), int(m[1][0]), int(m[1][1])
    especificidad = vn / max(1, vn + fp)
    tasa_fp = fp / max(1, vn + fp)
    tasa_fn = fn / max(1, fn + vp)
    estilos.indicadores([
        ("VN", "Especificidad", f"{especificidad:.1%}", f"{vn:,} normales sin falsa alarma", "ok"),
        ("FP", "Falsas alarmas", f"{tasa_fp:.1%}", f"{fp:,} normales marcados como ataque",
         "ok" if tasa_fp < 0.05 else "medio"),
        ("FN", "Ataques no vistos", f"{tasa_fn:.1%}", f"{fn:,} ataques sin alerta: el error caro",
         "mal" if tasa_fn > 0.2 else "medio"),
        ("VP", "Ataques detectados", f"{vp:,}", f"de {vp + fn:,} ataques reales", "marca"),
        ("5C", "Exactitud 5 clases", f"{float(multi.get('accuracy', 0)):.1%}",
         f"F1 ponderado {float(multi.get('weighted_f1', 0)):.3f}", "indigo"),
        ("ms", "Latencia en lote", f"{float(latencia.get('ms_por_fila_en_lote_500', 0)):.2f} ms",
         f"por fila en lote, frente a {float(latencia.get('ms_por_fila_sola', 0)):.0f} ms sola", "cielo"),
        ("IF", "Isolation Forest", f"AUC {float(iforest.get('auc_roc', 0)):.3f}",
         "no supervisado, solo tráfico normal", "rosa"),
        ("10", "Rareza top 10 %",
         f"{float(iforest.get('recall_ataques_top10_por_ciento', 0)):.1%}",
         "de los ataques cae en el décimo más raro", "rosa"),
    ])


def _reporte(api: str, estado: dict, metricas: dict, resumen: dict) -> None:
    """Botón de descarga del reporte para la defensa, armado con datos de la API."""
    texto = reporte_markdown(api, estado, metricas, resumen)
    col1, col2 = st.columns([3, 1], vertical_alignment="center")
    col1.caption("Reporte en Markdown con estado, métricas, criterios y veredictos, "
                 "generado ahora desde la API. Ábrelo en cualquier editor o pégalo en tu informe.")
    col2.download_button(
        "Reporte para la defensa", texto.encode("utf-8"),
        file_name=f"reporte_red_centinela_{pd.Timestamp.now(tz='UTC'):%Y%m%d_%H%M}.md",
        mime="text/markdown", icon=":material/description:", width="stretch",
        key="dl_reporte",
    )


def reporte_markdown(api: str, estado: dict, metricas: dict, resumen: dict) -> str:
    """Arma el reporte. Cada cifra sale de /health, /metrics o /history/resumen."""
    binario = metricas.get("binario_kddtest") or {}
    multi = metricas.get("multiclase_kddtest") or {}
    dificil = (metricas.get("kddtest21") or {}).get("binario") or {}
    familias = metricas.get("recall_por_familia") or {}
    latencia = metricas.get("latencia") or {}

    def cifra(valor, formato=".4f") -> str:
        return "sin datos" if valor is None else format(float(valor), formato)

    macro = binario.get("macro_f1")
    lineas = [
        "# Red Centinela, reporte para la defensa",
        "",
        f"Generado: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC desde `{api}`.",
        "",
        "## Estado del servicio",
        "",
        f"- Servicio: **{estado.get('status', '?')}**, versión {estado.get('version', '?')}",
        f"- Modelos cargados: {'sí' if estado.get('modelos_disponibles') else 'no'}",
        (f"- Integridad de artefactos (SHA-256): "
        f"{'íntegros' if estado.get('integridad_artefactos') else 'no verificados'}"),
        f"- Umbral de decisión: {estado.get('umbral_decision') or 'sin datos'}",
        f"- Almacén: {(estado.get('almacen') or {}).get('motor', '?')}",
        (f"- Historial: {int(resumen.get('total', 0)):,} predicciones, "
        f"{int(resumen.get('ataques', 0)):,} ataques"),
        "",
        "## Métricas sobre KDDTest+ (22,544 filas no vistas)",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Macro-F1 binario | {cifra(macro)} |",
        f"| Exactitud | {cifra(binario.get('accuracy'))} |",
        f"| Precisión de ataque | {cifra(binario.get('precision_ataque'))} |",
        f"| Recall de ataque | {cifra(binario.get('recall_ataque'))} |",
        f"| AUC ROC | {cifra(binario.get('auc_roc'))} |",
        f"| Macro-F1 cinco clases | {cifra(multi.get('macro_f1'))} |",
        f"| Macro-F1 KDDTest-21 | {cifra(dificil.get('macro_f1'))} |",
        "",
        "## Recall por familia",
        "",
        "| Familia | Detección | Clasificación |",
        "|---|---|---|",
    ]
    for c in CLASES[1:]:
        fila = familias.get(c) or {}
        lineas.append(f"| {c} | {cifra(fila.get('recall_deteccion'))} | "
                      f"{cifra(fila.get('recall_clasificacion'))} |")
    cumple = macro is not None and float(macro) >= 0.90
    lineas += [
        "",
        "## Criterios",
        "",
        "| Criterio | Exigencia | Medido | Veredicto |",
        "|---|---|---|---|",
        (f"| PERF-003 | macro-F1 ≥ 0.90 en KDDTest+ | {cifra(macro)} | "
        f"{'cumplido' if cumple else 'no cumplido'} |"),
        (f"| Integridad | artefactos coinciden con el manifiesto | "
        f"{'íntegros' if estado.get('integridad_artefactos') else 'no verificados'} | "
        f"{'cumplido' if estado.get('integridad_artefactos') else 'no cumplido'} |"),
        (f"| Latencia | ≤ 200 ms p95 | {cifra(latencia.get('ms_por_fila_sola'), '.0f')} ms por "
        "fila (desarrollo) | no cumplido en desarrollo |"),
        "| ALERT-010 | mensaje confirmado en Telegram | sin token ni chat_id | no evidenciado |",
        "| DEPLOY-013 | URL pública | sin cuentas | pendiente |",
        "",
        ("El modelo no se ajustó contra KDDTest+. El umbral se calibró sobre un holdout "
        "interno. La solicitud de cambio de PERF-003 está en "
        "`docs/SOLICITUD_CAMBIO_PERF-003.md`."),
        "",
    ]
    return "\n".join(lineas)


def _render_actividad(api: str) -> None:
    # Se relee aquí (y no se recibe del render) para que la actualización
    # automática del fragmento traiga también los totales nuevos.
    resumen = datos.resumen(api) or {}
    total = int(resumen.get("total", 0))
    por_clase = resumen.get("por_clase") or {}
    sin_familia = int(resumen.get("sin_familia", 0) or 0)
    ataques = int(resumen.get("ataques", 0))
    df = datos.historial_df(api, client.HISTORIAL_MAXIMO)
    if df.empty:
        estilos.vacio(
            "Todavía no hay tráfico analizado",
            "Analiza una conexión o sube un CSV en la vista <strong>Analizar</strong>: "
            "la actividad por hora, la postura reciente y las últimas predicciones "
            "aparecerán aquí. El panorama del modelo de arriba ya usa cifras reales.",
        )
        return

    izquierda, derecha = st.columns([5, 4], gap="large")
    with izquierda:
        st.altair_chart(graficas.actividad(df), width="stretch")
        estilos.fuente(
            f"{len(df):,} predicciones entre "
            f"{df['momento'].min():%d/%m %H:%M} y {df['momento'].max():%d/%m %H:%M} (UTC). "
            "Una hora sin barra es una hora sin tráfico analizado, no un fallo."
        )
    with derecha:
        serie = pd.DataFrame({
            "clase": CLASES,
            "registros": [int(por_clase.get(c, 0)) for c in CLASES],
        })
        st.altair_chart(graficas.dona(serie), width="stretch")
        estilos.fuente("Composición del historial completo por familia predicha.")

    # ------------------------------------------------------------------
    estilos.seccion("5", "Postura reciente", "últimas 50 predicciones")
    recientes = df.sort_values("id", ascending=False).head(50)
    n = len(recientes)
    ataques_rec = recientes[recientes["es_ataque"]]
    tasa = 100.0 * len(ataques_rec) / max(1, n)
    if tasa >= 50:
        nivel, tono = "alta", True
    elif tasa >= 15:
        nivel, tono = "media", True
    else:
        nivel, tono = "baja", False
    # La cabeza multiclase puede devolver "normal" en un ataque que el binario sí
    # detectó. Elegir la moda sin filtrar hacía que "Familia dominante" dijera
    # "Normal", que es una contradicción en la misma tarjeta.
    con_familia_rec = ataques_rec[ataques_rec["clase"] != "normal"]
    if con_familia_rec.empty:
        familia_top = "sin clasificar"
        nota_familia = ("ningún ataque reciente tiene familia asignada"
                        if not ataques_rec.empty else "sin ataques en la ventana")
    else:
        familia_top = con_familia_rec["clase"].value_counts().idxmax()
        sin_rec = len(ataques_rec) - len(con_familia_rec)
        nota_familia = (f"{sin_rec} de {len(ataques_rec)} ataques recientes sin familia"
                        if sin_rec else "la más frecuente entre los ataques recientes")
    ultimo = (ataques_rec["hora"].iloc[0] if not ataques_rec.empty else "sin ataques")
    estilos.kpis([
        ("Actividad hostil", nivel, f"{tasa:.0f} % de ataques en {n} registros", tono),
        ("Familia dominante", NOMBRE_CLASE.get(familia_top, familia_top).split(" (")[0],
         nota_familia),
        ("Último ataque", ultimo, "hora UTC del registro"),
        ("p(ataque) media", f"{recientes['probabilidad_ataque'].mean():.3f}",
         "promedio de las últimas predicciones"),
    ])
    estilos.fuente("Nivel heurístico del tablero: baja < 15 %, media < 50 %, alta ≥ 50 % de "
                   "ataques en la ventana. No es una métrica del modelo.")

    # ------------------------------------------------------------------
    estilos.seccion("6", "Composición por clase", "historial completo")
    if por_clase:
        filas = []
        for clase in CLASES:
            c_n = int(por_clase.get(clase, 0))
            filas.append({
                "Clase": NOMBRE_CLASE[clase],
                "Código": clase,
                "Registros": f"{c_n:,}",
                "Participación": f"{100.0 * c_n / max(1, total):.1f} %",
            })
        izquierda, derecha = st.columns([3, 2], gap="large")
        with izquierda:
            estilos.tabla(filas, ["Clase", "Código", "Registros", "Participación"],
                          numericas=("Registros", "Participación"), fuertes=("Clase",))
        with derecha:
            estilos.barras(
                [(NOMBRE_CLASE[c].split(" ")[0], int(por_clase.get(c, 0)),
                  f"{int(por_clase.get(c, 0)):,}", "ok" if c == "normal" else "mal")
                 for c in CLASES],
                escala=float(max(int(por_clase.get(c, 0)) for c in CLASES) or 1),
            )
            estilos.fuente("R2L y U2R son las familias con menos registros y menos recall, y "
                           "el detalle está en Modelo y métricas.")
        if sin_familia:
            estilos.bloque(
                "Por qué los ataques no cuadran con la suma de familias.",
                f"{sin_familia:,} de los {ataques:,} ataques están marcados por la cabeza "
                "binaria pero la cabeza multiclase no los reconoce como DoS, Probe, R2L ni "
                "U2R: quedan con clase normal y no aparecen en la tabla de arriba. No es un "
                "error de suma. Son ataques que no se parecen a ninguna familia vista en "
                "entrenamiento, que es justo el caso de R2L y U2R. El historial guardado no "
                "se reescribe: se cuenta aparte.",
                tono="nota",
            )

    # ------------------------------------------------------------------
    estilos.seccion("7", "Últimas predicciones", "lo que acaba de pasar")
    ultimas = df.sort_values("id", ascending=False).head(8)
    estilos.tabla(
        [{
            "ID": int(f.id),
            "Hora (UTC)": f.hora,
            "Origen": f.origen,
            "Clase": f.clase,
            "p(ataque)": f"{f.probabilidad_ataque:.4f}",
            "Alerta": "sí" if f.alerta_enviada else "no",
        } for f in ultimas.itertuples()],
        ["ID", "Hora (UTC)", "Origen", "Clase", "p(ataque)", "Alerta"],
        numericas=("ID", "p(ataque)"), fuertes=("Clase",),
    )
    estilos.fuente("Ocho registros más recientes. El historial completo está en la vista Historial.")


def _bloque_alertas(api: str) -> None:
    st.subheader("Alertas por Telegram")
    estado = datos.alertas(api) or {}
    if not estado.get("configurado"):
        estilos.bloque(
            "Bot sin configurar.",
            "La API no tiene <span class='rc-mono'>REDCENTINELA_TELEGRAM_TOKEN</span> "
            "ni <span class='rc-mono'>REDCENTINELA_TELEGRAM_CHAT_ID</span>. No se "
            "envía nada y el historial lo refleja con <em>alerta_enviada = falso</em>.",
        )
        return

    estilos.kpis([
        ("Enviados", f"{int(estado.get('enviados', 0)):,}", "confirmados por el Bot API"),
        ("Fallidos", f"{int(estado.get('fallidos', 0)):,}", "rechazos o red"),
        ("En cola", f"{int(estado.get('pendientes', 0)):,}",
         f"ventana de {estado.get('ventana_agrupacion_segundos', '?')} s"),
    ], alerta=(1,))

    if not auth.puede_escribir(st.session_state):
        estilos.sin_permiso("enviar el mensaje de prueba")
        return
    if st.button("Enviar mensaje de prueba", key="btn_alerta_prueba"):
        with st.spinner("Pidiendo a la API que envíe el mensaje..."):
            try:
                r = client.alerta_prueba()
            except client.ApiError as exc:
                st.error(str(exc))
            else:
                if r.get("ok"):
                    st.success(
                        f"Telegram aceptó el mensaje (message_id {r.get('message_id')}). "
                        "Revísalo en el chat: la confirmación final es visual."
                    )
                else:
                    st.error(f"El Bot API rechazó el envío: {r.get('detalle') or r}")
        datos.invalidar()


def _bloque_integridad(api: str, estado: dict) -> None:
    st.subheader("Integridad de los artefactos")
    modelo = ", ".join(estado.get("modelo") or []) or "?"
    st.caption(
        f"Modelo {modelo} versión {estado.get('version_modelo', '?')}. "
        "La verificación compara el SHA-256 de cada .joblib contra el manifiesto."
    )
    if st.button("Reverificar artefactos ahora", key="btn_reverificar"):
        with st.spinner("Hasheando 80 MB de artefactos..."):
            nuevo = datos.salud(api, reverificar=True)
        if nuevo is None:
            st.error("La API no respondió durante la reverificación.")
        elif nuevo.get("integridad_artefactos"):
            st.success("Los cinco artefactos coinciden con el manifiesto.")
        else:
            st.error(
                "El manifiesto no coincide. Alguien reemplazó o borró un modelo: "
                "revisa motor/models/ antes de usar esta API."
            )
        datos.invalidar()


def _bloque_rendimiento(macro_f1, binario: dict) -> None:
    st.subheader("Criterio de rendimiento (PERF-003)")
    if macro_f1 is None:
        st.info("La API no publicó métricas del modelo.")
        return
    valor = float(macro_f1)
    st.progress(min(1.0, max(0.0, valor)),
                text=f"Macro-F1 de {valor:.4f} frente a la meta de 0.9000")
    estilos.barras([
        ("Macro-F1 binario", valor, f"{valor:.4f}", "mal" if valor < 0.90 else "ok"),
        ("Precisión de ataque", float(binario.get("precision_ataque", 0)),
         f"{float(binario.get('precision_ataque', 0)):.4f}", "ok"),
        ("Recall de ataque", float(binario.get("recall_ataque", 0)),
         f"{float(binario.get('recall_ataque', 0)):.4f}", "medio"),
        ("AUC ROC", float(binario.get("auc_roc", 0)),
         f"{float(binario.get('auc_roc', 0)):.4f}", "ok"),
    ])
    if valor < 0.90:
        st.caption(
            "Meta no cumplida sobre KDDTest+. No se ajustó el modelo contra ese "
            "conjunto: la diferencia mide generalización, no un error de código. "
            "Ver la solicitud de cambio en docs/SOLICITUD_CAMBIO_PERF-003.md."
        )
