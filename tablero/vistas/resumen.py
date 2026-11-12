"""Vista 1: resumen operativo del servicio."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero import client
from tablero.ui import datos, estilos

CLASES = ["normal", "dos", "probe", "r2l", "u2r"]


def render() -> None:
    api = datos.api_actual()
    estilos.encabezado(
        "Resumen operativo",
        "Estado del servicio, volumen de tráfico analizado y alertas. "
        "Las cifras salen de la API, no de este navegador.",
    )

    estado = datos.salud(api)
    estilos.estado_servicio(estado)
    if estado is None:
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
    normales = int(resumen.get("normales", 0))
    proporcion = (100.0 * ataques / total) if total else 0.0

    estilos.kpis([
        ("Predicciones", f"{total:,}", "historial persistido" if
         (resumen.get("almacen") or {}).get("persistente") else "historial local"),
        ("Ataques", f"{ataques:,}", "es_ataque = verdadero", 1),
        ("Normales", f"{normales:,}", "tráfico sin hallazgos"),
        ("Proporción de ataque", f"{proporcion:.1f} %", "sobre el total"),
    ], alerta=(1,))

    if total == 0:
        estilos.bloque(
            "Todavía no hay historial.",
            "Analiza una conexión o sube un CSV en la vista <strong>Analizar</strong> "
            "y las cifras aparecerán aquí.",
        )

    izquierda, derecha = st.columns([3, 2], gap="large")

    with izquierda:
        st.subheader("Predicciones recientes")
        ultimas = datos.historial(api, 60) or []
        if ultimas:
            df = pd.DataFrame(ultimas)
            df["hora"] = pd.to_datetime(df["ts"], errors="coerce", utc=True).dt.strftime(
                "%d/%m %H:%M:%S"
            )
            st.line_chart(
                df.sort_values("id").set_index("id")["probabilidad_ataque"],
                height=190, color="#0f5c4a",
            )
            st.caption("Probabilidad de ataque por predicción, en orden de llegada.")
            st.dataframe(
                df[["id", "hora", "origen", "clase", "probabilidad_ataque", "alerta_enviada"]],
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "hora": st.column_config.TextColumn("Hora (UTC)"),
                    "origen": st.column_config.TextColumn("Origen"),
                    "clase": st.column_config.TextColumn("Clase"),
                    "probabilidad_ataque": st.column_config.ProgressColumn(
                        "p(ataque)", min_value=0.0, max_value=1.0, format="%.4f"
                    ),
                    "alerta_enviada": st.column_config.CheckboxColumn("Alerta"),
                },
                height=330,
            )
        else:
            st.info("Sin predicciones registradas todavía.")

    with derecha:
        st.subheader("Composición por clase")
        por_clase = (resumen.get("por_clase") or {})
        if por_clase:
            serie = pd.Series({c: int(por_clase.get(c, 0)) for c in CLASES})
            st.bar_chart(serie, height=200, color="#0f5c4a")
            st.caption(
                "Clasificación de la cabeza multiclase. Un ataque detectado puede "
                "quedar en la familia equivocada: eso se mide en Modelo y métricas."
            )
        else:
            st.info("Sin datos de clase.")

        _bloque_alertas(api)
        _bloque_integridad(api, estado)


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
