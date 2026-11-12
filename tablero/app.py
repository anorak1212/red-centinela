"""Tablero Streamlit de Red Centinela.

    streamlit run tablero/app.py

Multipágina con `st.navigation`, agrupada en tres secciones: Operación (lo que
se usa en la demo), Modelo (lo que se interroga) y Proyecto (lo que se
declara). El tablero solo habla con la API REST: no carga modelos ni abre la
base de datos, así que se despliega con tres dependencias y puede apuntarse a
la API local o a la de producción cambiando la URL de la barra lateral.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    # `streamlit run tablero/app.py` pone tablero/ en sys.path, no la raíz del
    # repositorio. Sin esto, `import tablero` falla al desplegar en la nube.
    sys.path.insert(0, str(RAIZ))

from tablero import __version__, auth, client, guia, navegacion
from tablero.ui import datos, estilos

st.set_page_config(
    page_title="Red Centinela",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)
estilos.aplicar()

# Se arman en cada ejecución del script (ver tablero/navegacion.py).
PAGINAS = navegacion.paginas()




def _pantalla_login() -> None:
    """Formulario de acceso. Se muestra solo si hay usuarios configurados."""
    estilos.ocultar_barra_lateral()
    _, centro, _ = st.columns([1, 1.15, 1])
    with centro:
        estilos.marca_login(__version__)
        bloqueo = auth.segundos_bloqueado(st.session_state)
        with st.form("form_login", border=True):
            st.markdown("**Iniciar sesión**")
            nombre = st.text_input("Usuario", autocomplete="username")
            clave = st.text_input("Contraseña", type="password",
                                  autocomplete="current-password")
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch",
                                           icon=":material/login:", disabled=bloqueo > 0)
        if bloqueo > 0:
            st.error(f"Demasiados intentos fallidos. Espera {bloqueo} s y recarga la página.")
        elif entrar:
            usuario = auth.autenticar(auth.cargar_usuarios(), nombre, clave)
            if usuario is None:
                auth.registrar_fallo(st.session_state)
                st.error("Usuario o contraseña incorrectos.")
            else:
                auth.iniciar_sesion(st.session_state, usuario)
                st.rerun()
        st.caption(
            f"Después de {auth.INTENTOS_MAXIMOS} intentos fallidos el acceso se bloquea "
            f"{auth.BLOQUEO_SEGUNDOS} s. La sesión dura {auth.SESION_HORAS} h."
        )


def _navegacion() -> None:
    """Menú propio debajo del logo (el nativo siempre va arriba de todo)."""
    for seccion, paginas in PAGINAS.items():
        st.markdown(f'<p class="rc-nav-seccion">{seccion}</p>', unsafe_allow_html=True)
        for pagina in paginas:
            st.page_link(pagina, width="stretch")


def _sesion() -> None:
    if not auth.configurado():
        estilos.bloque(
            "Acceso abierto.",
            f"Define <span class='rc-mono'>{auth.VARIABLE}</span> para exigir usuario "
            "y contraseña.",
            tono="atencion",
        )
        return
    sesion = auth.usuario_actual(st.session_state) or {}
    col1, col2 = st.columns([3, 2], vertical_alignment="center")
    col1.markdown(
        estilos.pill(sesion.get("nombre", "?"), "marca")
        + estilos.pill(sesion.get("rol", "?"), "neutra"),
        unsafe_allow_html=True,
    )
    if col2.button("Salir", icon=":material/logout:", key="btn_salir", width="stretch"):
        auth.cerrar_sesion(st.session_state)
        st.rerun()
    if sesion.get("texto_plano"):
        st.caption("Tu contraseña está en texto plano en la configuración. "
                   "Genera un hash con `python -m tablero.auth`.")


def _barra_lateral() -> None:
    with st.sidebar:
        estilos.marca(__version__)
        _navegacion()
        st.divider()
        guia.interruptores()
        st.divider()

        url = st.session_state.get("api_url", client.api_url())
        client.configurar(url)
        estado = datos.salud(url)
        # La tarjeta se llena al final, después de atender los botones, para que
        # la latencia recién medida aparezca en este mismo clic.
        tarjeta = st.empty()

        with st.expander("Conexión con la API", icon=":material/lan:",
                         expanded=estado is None):
            nueva = st.text_input(
                "URL de la API",
                value=url,
                help="Local por omisión. En la demo apunta aquí a la API desplegada.",
            )
            if nueva.strip().rstrip("/") != url:
                st.session_state["api_url"] = nueva.strip().rstrip("/") or url
                st.session_state.pop("latencia_ms", None)
                datos.invalidar()
                st.rerun()

            col1, col2 = st.columns(2)
            comprobar = col1.button("Comprobar conexión", type="primary", width="stretch",
                                    help="Mide la latencia real de /health")
            despertar = col2.button("Despertar servicio", width="stretch",
                                    help="Sondea /health hasta 90 s")
            if comprobar:
                datos.invalidar()
                inicio = time.perf_counter()
                ok, _ = client.esperar_api(segundos=20)
                estado = datos.salud(url)
                if ok:
                    st.session_state["latencia_ms"] = (time.perf_counter() - inicio) * 1000
                    ms = st.session_state["latencia_ms"]
                    st.success(f"API en línea, respondió en {'<1' if ms < 1 else f'{ms:.0f}'} ms.")
                else:
                    st.session_state.pop("latencia_ms", None)
                    st.error("Sin respuesta en 20 s.")
            if despertar:
                with st.spinner("Sondeando /health..."):
                    ok, segundos = client.esperar_api(segundos=90)
                datos.invalidar()
                estado = datos.salud(url)
                if ok:
                    st.success(f"Servicio despierto en {segundos:.0f} s.")
                else:
                    st.error("No despertó en 90 s. Revisa el panel del proveedor.")

        with tarjeta.container():
            estilos.tarjeta_conexion(url, estado, st.session_state.get("latencia_ms"))

        if st.button("Recargar datos", icon=":material/refresh:", width="stretch",
                     help="Vacía la caché y vuelve a pedir todo a la API"):
            datos.invalidar()
            st.rerun()

        st.caption(
            "Los datos son los de la API, no los de esta sesión. Caché de 10 s "
            "para historial y estado, 5 min para métricas."
        )
        st.divider()
        _sesion()


if auth.configurado() and auth.usuario_actual(st.session_state) is None:
    _pantalla_login()
    st.stop()

pagina_actual = st.navigation(PAGINAS, position="hidden")
_barra_lateral()
guia.panel(pagina_actual)
pagina_actual.run()
