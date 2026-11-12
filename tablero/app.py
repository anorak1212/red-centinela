"""Tablero Streamlit de Red Centinela.

    streamlit run tablero/app.py

Multipágina con `st.navigation`. El tablero solo habla con la API REST: no
carga modelos ni abre la base de datos, así que se despliega con tres
dependencias y puede apuntarse a la API local o a la de producción cambiando
la URL de la barra lateral.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    # `streamlit run tablero/app.py` pone tablero/ en sys.path, no la raíz del
    # repositorio. Sin esto, `import tablero` falla al desplegar en la nube.
    sys.path.insert(0, str(RAIZ))

from tablero import __version__, client
from tablero.ui import datos, estilos
from tablero.vistas import analizar, ayuda, historial, modelo, resumen

st.set_page_config(
    page_title="Red Centinela",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)
estilos.aplicar()


def _barra_lateral() -> None:
    with st.sidebar:
        st.markdown(
            f'<p class="rc-titulo" style="font-size:1.2rem">Red Centinela</p>'
            f'<p class="rc-sub" style="margin-bottom:.6rem">Tablero v{__version__}</p>',
            unsafe_allow_html=True,
        )

        url = st.text_input(
            "URL de la API",
            value=st.session_state.get("api_url", client.api_url()),
            help="Local por omisión. En la demo apunta aquí a la API desplegada.",
        )
        st.session_state["api_url"] = url
        client.configurar(url)

        if st.button("Comprobar conexión", type="primary"):
            datos.invalidar()
            ok, segundos = client.esperar_api(segundos=20)
            if ok:
                st.success(f"API en línea ({segundos:.0f} s).")
            else:
                st.error("Sin respuesta en 20 s.")

        if st.button("Despertar servicio", help="Sondea /health hasta 90 s"):
            with st.spinner("Sondeando /health..."):
                ok, segundos = client.esperar_api(segundos=90)
            if ok:
                st.success(f"Servicio despierto en {segundos:.0f} s.")
                datos.invalidar()
            else:
                st.error("No despertó en 90 s. Revisa el panel del proveedor.")

        estado = datos.salud(url)
        estilos.estado_servicio(estado)

        st.divider()
        st.caption(
            "Atajos: `R` recarga el script, `C` limpia la caché. Los datos del "
            "tablero son los de la API, no los de esta sesión."
        )


_barra_lateral()

paginas = [
    st.Page(resumen.render, title="Resumen", icon=":material/dashboard:",
            url_path="resumen", default=True),
    st.Page(analizar.render, title="Analizar", icon=":material/radar:",
            url_path="analizar"),
    st.Page(historial.render, title="Historial", icon=":material/history:",
            url_path="historial"),
    st.Page(modelo.render, title="Modelo y métricas", icon=":material/insights:",
            url_path="modelo"),
    st.Page(ayuda.render, title="Ayuda", icon=":material/help:",
            url_path="ayuda"),
]
st.navigation(paginas).run()
