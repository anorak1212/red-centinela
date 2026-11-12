"""Configuración del tablero: apariencia, comportamiento y conexión.

Todo lo que se cambia aquí aplica de inmediato y vale para esta sesión del
navegador. No toca la API ni el modelo: el umbral de decisión, por ejemplo,
sigue siendo el calibrado (para explorar otro está el simulador de Historial).
"""

from __future__ import annotations

import json

import streamlit as st

from tablero import __version__, auth, client
from tablero.ui import datos, estilos, preferencias


def render() -> None:
    estilos.encabezado(
        "Configuración",
        "Apariencia y comportamiento del tablero. Los cambios aplican al instante y "
        "duran lo que dure esta sesión del navegador.",
        eyebrow="Ajustes",
    )

    apariencia, comportamiento, conexion = st.tabs([
        ":material/palette: Apariencia", ":material/tune: Comportamiento",
        ":material/lan: Conexión y sesión",
    ])
    with apariencia:
        _apariencia()
    with comportamiento:
        _comportamiento()
    with conexion:
        _conexion()

    estilos.seccion("4", "Resumen de la configuración", "lo que está activo ahora")
    actual = dict(st.session_state.get("preferencias") or preferencias.POR_OMISION)
    estilos.indicadores([
        ("TM", "Tema", actual["tema"], "claro u oscuro", "indigo"),
        ("AC", "Acento", actual["acento"], "color de marca y acciones", "marca"),
        ("MV", "Animaciones", "activas" if actual["animaciones"] else "apagadas",
         "entrada, radar y barras", "cielo"),
        ("DN", "Densidad", actual["densidad"], "espaciado de tarjetas y tablas", "rosa"),
        ("RF", "Actualización", f"{actual['intervalo_auto']} s", "Resumen, si se activa", "ok"),
        ("LT", "Lote", f"{actual['tamano_lote']} filas", "por petición a /predict/batch", "medio"),
        ("PR", "Presentación", "activa" if actual.get("presentacion") else "apagada",
         "letra grande para proyectar", "marca"),
    ])
    col1, col2, _ = st.columns([1.2, 1.4, 2])
    if col1.button("Restablecer valores", icon=":material/restart_alt:", width="stretch",
                   key="btn_restablecer"):
        restablecer()
        st.rerun()
    col2.download_button(
        "Exportar configuración", json.dumps(actual, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="configuracion_tablero.json", mime="application/json",
        icon=":material/download:", width="stretch", key="dl_config",
    )


def restablecer() -> None:
    preferencias.restablecer()
    for clave in list(st.session_state):
        if clave.startswith("cfg_"):
            del st.session_state[clave]


def _control(clave: str, widget, *args, **kwargs):
    """Dibuja un control ligado a una preferencia y la guarda si cambió."""
    valor = widget(*args, key=f"cfg_{clave}", **kwargs)
    if valor is not None and valor != preferencias.obtener(clave):
        preferencias.fijar(clave, valor)
        st.rerun()
    return valor


def _apariencia() -> None:
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _control("tema", st.segmented_control, "Tema", list(preferencias.TEMAS),
                 default=preferencias.obtener("tema"),
                 help="Oscuro reduce el brillo para salas con proyector o de noche.")
        _control("acento", st.radio, "Color de acento", list(preferencias.ACENTOS),
                 index=list(preferencias.ACENTOS).index(preferencias.obtener("acento")),
                 horizontal=True,
                 help="Cambia la marca, los botones y las barras informativas. Los colores "
                      "de estado (verde, ámbar, rojo) no cambian: son información.")
    with derecha:
        _control("densidad", st.segmented_control, "Densidad", list(preferencias.DENSIDADES),
                 default=preferencias.obtener("densidad"),
                 help="Compacta reduce márgenes para ver más en una pantalla.")
        _control("animaciones", st.toggle, "Animaciones",
                 value=bool(preferencias.obtener("animaciones")),
                 help="Entrada escalonada, radar de la portada y barras que crecen.")
        _control("presentacion", st.toggle, "Modo presentación",
                 value=bool(preferencias.obtener("presentacion")),
                 help="Letra más grande y sin notas secundarias, para proyectar en la defensa. "
                      "También está en la barra lateral.")
    st.markdown("**Vista previa**")
    principal = preferencias.acento()[0]
    estilos.indicadores([
        ("OK", "Normal o cumplido", "verde azulado", "estado sano", "ok"),
        ("!", "Umbral o atención", "ámbar", "revisar", "medio"),
        ("AT", "Ataque o incumplido", "rojo", "acción necesaria", "mal"),
        ("AC", "Acento", preferencias.obtener("acento"), principal, "marca"),
    ])


def _comportamiento() -> None:
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _control("intervalo_auto", st.select_slider, "Actualización automática del Resumen",
                 options=[10, 15, 30, 60], value=int(preferencias.obtener("intervalo_auto")),
                 format_func=lambda v: f"{v} s",
                 help="Cada cuánto se relee /history cuando el interruptor de Resumen está activo.")
        opciones = [100, 250, client.HISTORIAL_MAXIMO]
        actual = int(preferencias.obtener("limite_historial"))
        _control("limite_historial", st.radio, "Registros que abre Historial", opciones,
                 index=opciones.index(actual) if actual in opciones else 1, horizontal=True,
                 help=f"La API devuelve como máximo {client.HISTORIAL_MAXIMO} por consulta.")
    with derecha:
        _control("tamano_lote", st.select_slider, "Filas por petición al analizar un CSV",
                 options=[50, 100, 200, 300, 500], value=int(preferencias.obtener("tamano_lote")),
                 help="Lotes más chicos dan una barra de progreso más fina y los más grandes, "
                      f"menos peticiones. Máximo de la API: {client.LOTE_MAXIMO}.")
        if st.button("Vaciar caché de datos", icon=":material/cleaning_services:",
                     key="btn_cfg_cache"):
            datos.invalidar()
            st.success("Caché vaciada: la próxima lectura va directo a la API.")
    estilos.bloque(
        "Lo que no se configura aquí.",
        "El umbral de decisión (0.41), los nombres de los endpoints y las métricas son del "
        "modelo y de la API, no del tablero. Para ver qué pasaría con otro umbral usa el "
        "simulador de la vista Historial.",
    )


def _conexion() -> None:
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        st.markdown("**API**")
        url = st.session_state.get("api_url", client.api_url())
        estilos.tabla(
            [{"Dato": "URL", "Valor": url},
             {"Dato": "Versión del tablero", "Valor": __version__},
             {"Dato": "Tiempo de espera", "Valor": f"{client.TIMEOUT} s por petición"}],
            ["Dato", "Valor"], fuertes=("Dato",),
        )
        st.caption("La URL se cambia en la barra lateral, en Conexión con la API.")
    with derecha:
        st.markdown("**Sesión**")
        if not auth.configurado():
            estilos.bloque("Acceso abierto.",
                           f"Define <span class='rc-mono'>{auth.VARIABLE}</span> para exigir "
                           "usuario y contraseña.", tono="atencion")
        else:
            sesion = auth.usuario_actual(st.session_state) or {}
            estilos.tabla(
                [{"Dato": "Usuario", "Valor": sesion.get("nombre", "?")},
                 {"Dato": "Rol", "Valor": sesion.get("rol", "?")},
                 {"Dato": "Puede predecir", "Valor": "sí" if auth.puede_escribir(st.session_state)
                  else "no (solo lectura)"},
                 {"Dato": "Duración de la sesión", "Valor": f"{auth.SESION_HORAS} h"}],
                ["Dato", "Valor"], fuertes=("Dato",),
            )
