"""Recorrido guiado de la demo y modo presentación.

El recorrido es el guion de la defensa: siete pasos, cada uno en su vista, con
qué mostrar y qué decir. "Siguiente" cambia de vista de verdad, así que en la
demo se avanza con un solo botón y sin perder el hilo.
"""

from __future__ import annotations

import streamlit as st

from tablero import navegacion
from tablero.ui import estilos, preferencias

PASOS = [
    ("resumen", "El servicio está vivo y se mide",
     "Muestra la portada y el panorama del modelo.",
     ("El macro-F1 es 0.7995 frente a una meta de 0.90. Se mide sobre 22,544 filas que el "
     "modelo nunca vio, y no se ajustó contra ellas.")),
    ("analizar", "Una conexión, una decisión",
     "Elige la fila DoS y pulsa Predecir. Luego repite con la fila R2L.",
     ("DoS se detecta con claridad. R2L muestra el límite real del modelo, y se dice antes de "
     "que lo pregunten.")),
    ("analizar", "Un lote con verdad conocida",
     "En la pestaña Archivo CSV descarga la muestra etiquetada, súbela y predice las 150 filas.",
     "La matriz del lote separa detectar un ataque de nombrar bien su familia."),
    ("historial", "La memoria del sistema",
     "Filtra por clase y mueve el simulador de umbral.",
     ("Bajar el umbral atrapa más ataques a cambio de más falsas alarmas. El umbral oficial "
     "se calibró en el holdout, no en la prueba.")),
    ("modelo", "Lo que interroga el jurado",
     "Cambia la matriz binaria entre KDDTest+ y KDDTest-21.",
     "Que la cifra baje en el subconjunto difícil es la señal de que no hay fuga de datos."),
    ("sistema", "Qué existe y qué falta",
     "Pulsa Verificar endpoints ahora y recorre la tabla de criterios.",
     "Cada criterio va con la cifra medida y su veredicto, incluidos los que no se cumplen."),
    ("resumen", "El cierre",
     "Descarga el reporte para la defensa.",
     "Todo lo mostrado queda en un documento generado en vivo desde la API."),
]


def interruptores() -> None:
    """Controles rápidos de la barra lateral."""
    # El estado vive en "guia_activa" y no en la clave del widget: Streamlit
    # limpia el estado de los widgets al cambiar de página con switch_page.
    activo = st.toggle("Recorrido de la demo", value=bool(st.session_state.get("guia_activa")),
                       key="tg_guia",
                       help="Muestra el guion de la defensa paso a paso, arriba de cada vista.")
    if activo != bool(st.session_state.get("guia_activa")):
        st.session_state["guia_activa"] = activo
        st.session_state.setdefault("guia_paso", 0)
        st.rerun()
    presentacion = st.toggle("Modo presentación", value=bool(preferencias.obtener("presentacion")),
                             key="tg_presentacion",
                             help="Letra más grande y menos texto secundario, para proyectar.")
    if presentacion != preferencias.obtener("presentacion"):
        preferencias.fijar("presentacion", presentacion)
        st.rerun()


def panel(pagina_actual) -> None:
    """Tarjeta del paso actual, arriba de la vista."""
    if not st.session_state.get("guia_activa"):
        return
    paso = int(st.session_state.get("guia_paso", 0))
    paso = max(0, min(paso, len(PASOS) - 1))
    url, titulo, accion, guion = PASOS[paso]
    destino = navegacion.pagina(url)
    en_su_vista = navegacion.misma(pagina_actual, destino)

    with st.container(border=True):
        estilos.guia_cabecera(paso + 1, len(PASOS), titulo, accion, guion)
        c1, c2, c3, _ = st.columns([1, 1, 1.3, 2.7], vertical_alignment="center")
        if c1.button("Anterior", icon=":material/arrow_back:", disabled=paso == 0,
                     key="guia_anterior", width="stretch"):
            _ir(paso - 1, pagina_actual)
        ultimo = paso == len(PASOS) - 1
        if ultimo:
            c2.button("Terminar", type="primary", key="guia_terminar", icon=":material/check:",
                      width="stretch", on_click=_terminar)
        elif c2.button("Siguiente", type="primary", key="guia_siguiente",
                       icon=":material/arrow_forward:", width="stretch"):
            _ir(paso + 1, pagina_actual)
        if not en_su_vista and c3.button(f"Ir a {destino.title}", key="guia_ir",
                                         icon=":material/near_me:", width="stretch"):
            st.switch_page(destino)


def _terminar() -> None:
    # En un callback sí se puede reiniciar la clave del interruptor.
    st.session_state["guia_activa"] = False
    st.session_state["guia_paso"] = 0
    st.session_state["tg_guia"] = False


def _ir(paso: int, pagina_actual) -> None:
    st.session_state["guia_paso"] = paso
    destino = navegacion.pagina(PASOS[paso][0])
    if not navegacion.misma(destino, pagina_actual):
        st.switch_page(destino)
    st.rerun()
