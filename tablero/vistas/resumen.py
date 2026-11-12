"""Vista 1: resumen operativo del servicio.

Lo que un sinodal mira primero: cuánto tráfico pasó, cuánto fue ataque, qué
familias aparecieron y si el servicio está sano. Todo sale de la API; si la API
no responde, la vista lo dice en vez de dibujar ceros.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero import client
from tablero.ui import datos, estilos, graficas

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
    familias = [c for c in CLASES if c != "normal" and int(por_clase.get(c, 0)) > 0]
    metricas = datos.metricas(api) or {}
    binario = metricas.get("binario_kddtest") or {}
    macro_f1 = binario.get("macro_f1")

    estilos.banda(
        "Resumen operativo",
        "Servicio, tráfico analizado y alertas en una sola lectura. "
        "Cada cifra viene de /history/resumen y /metrics, no de esta sesión.",
        [
            (f"{total:,}", "Predicciones", "historial persistido de la API"),
            (f"{ataques:,}", "Ataques", "es_ataque = verdadero"),
            (f"{proporcion:.1f} %", "Tasa de ataque", "sobre el total registrado"),
            (f"{len(familias)}/4", "Familias detectadas", "de las cuatro de ataque"),
            (f"{float(macro_f1):.3f}" if macro_f1 is not None else "sin datos",
             "Macro-F1", "KDDTest+, meta 0.90"),
        ],
    )

    # ------------------------------------------------------------------
    estilos.seccion("1", "Estado del servicio", "verificado contra /health")
    estilos.estado_servicio(estado)
    almacen = estado.get("almacen") or {}
    estilos.kpis([
        ("Umbral de decisión", str(estado.get("umbral_decision", "?")),
         "calibrado sobre holdout interno"),
        ("Artefactos", "íntegros" if estado.get("integridad_artefactos") else "no verificados",
         "cinco .joblib contra el manifiesto SHA-256",
         not estado.get("integridad_artefactos")),
        ("Modelos cargados", ", ".join(estado.get("modelo") or []) or "?",
         f"versión {estado.get('version_modelo', '?')}"),
        ("Almacén", str(almacen.get("motor", "?")),
         "persistente" if almacen.get("persistente") else (almacen.get("nota") or "no persiste")),
    ])

    # ------------------------------------------------------------------
    estilos.seccion("2", "Actividad registrada", "últimas 500 predicciones")
    df = datos.historial_df(api, 500)
    if df.empty:
        estilos.bloque(
            "Todavía no hay historial.",
            "Analiza una conexión o sube un CSV en la vista <strong>Analizar</strong> "
            "y las cifras aparecerán aquí.",
        )
    else:
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
    estilos.seccion("3", "Composición por clase", "historial completo")
    if por_clase:
        filas = []
        for clase in CLASES:
            n = int(por_clase.get(clase, 0))
            filas.append({
                "Clase": NOMBRE_CLASE[clase],
                "Código": clase,
                "Registros": f"{n:,}",
                "Participación": f"{100.0 * n / max(1, total):.1f} %",
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
            estilos.fuente("R2L y U2R son las familias con menos registros y menos recall; "
                           "el detalle está en Modelo y métricas.")
    else:
        st.info("El historial todavía no tiene clases registradas.")

    # ------------------------------------------------------------------
    estilos.seccion("4", "Últimas predicciones", "lo que acaba de pasar")
    if not df.empty:
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
        estilos.fuente("Ocho registros más recientes de los 500 leídos. "
                       "El historial completo está en la vista Historial.")

    # ------------------------------------------------------------------
    estilos.seccion("5", "Dependencias del servicio", "alertas, artefactos y criterio de rendimiento")
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _bloque_alertas(api)
    with derecha:
        _bloque_integridad(api, estado)
        _bloque_rendimiento(macro_f1, binario)


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
                text=f"Macro-F1 {valor:.4f} · meta del proyecto 0.9000")
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
