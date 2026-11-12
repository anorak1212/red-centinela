"""Vista 5: qué hay detrás del tablero, cómo se ejecuta y qué mide cada cifra."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero import __version__
from tablero.ui import datos, estilos

ENDPOINTS = [
    ("GET", "/health", "Estado, integridad de artefactos y umbral. ?reverificar=true rehashea."),
    ("GET", "/metrics", "Cifras del modelo tomadas de metrics.json."),
    ("POST", "/predict", "Una conexión, 41 características, devuelve clase y probabilidad."),
    ("POST", "/predict/batch", "Hasta 500 conexiones por petición."),
    ("GET", "/history", "Predicciones guardadas. ?limit entre 1 y 500."),
    ("GET", "/history/resumen", "Conteos agregados que alimentan el resumen."),
    ("GET", "/alertas/estado", "Si el bot está configurado y cuántos mensajes salieron."),
    ("POST", "/alertas/prueba", "Envía un mensaje real al chat configurado."),
]

VARIABLES = [
    ("DATABASE_URL", "PostgreSQL (Neon). Sin ella, SQLite local que no persiste en la nube."),
    ("REDCENTINELA_DB", "Ruta alternativa del archivo SQLite."),
    ("REDCENTINELA_TELEGRAM_TOKEN", "Token del bot. Solo lo lee la API, nunca el tablero."),
    ("REDCENTINELA_TELEGRAM_CHAT_ID", "Chat destino de las alertas."),
    ("REDCENTINELA_API", "URL de la API que consume este tablero."),
    ("REDCENTINELA_RATE_LIMIT", "Peticiones por ventana y por IP en /predict (por omisión 120)."),
]


def render() -> None:
    estilos.encabezado(
        "Ayuda y estado del sistema",
        f"Tablero v{__version__}. Todo lo que muestra esta pantalla es verificable "
        "desde la API o desde el repositorio.",
    )

    tab_uso, tab_api, tab_limites = st.tabs(
        ["Cómo se ejecuta", "Contrato de la API", "Límites y decisiones"]
    )

    with tab_uso:
        st.markdown("**En local, dos procesos y un comando cada uno**")
        st.code(
            "python -m cli serve        # API en http://127.0.0.1:8000\n"
            "python -m cli estado       # comprueba salud e integridad\n"
            "streamlit run tablero/app.py",
            language="powershell",
        )
        st.markdown("**Pruebas y verificación**")
        st.code(
            "python -m pytest -q\n"
            "python -m coverage run -m pytest -q && python -m coverage report\n"
            "python -m scripts.smoke_prod --api http://127.0.0.1:8000",
            language="powershell",
        )
        st.markdown("**Despliegue**")
        estilos.bloque(
            "La API y el tablero son dos servicios.",
            "La API va en un servicio que ejecute Python (Render, con arranque en "
            "frío de unos 50 s en el plan gratuito). El tablero va en Streamlit "
            "Community Cloud apuntando a <span class='rc-mono'>REDCENTINELA_API</span>. "
            "Si la API se durmió, el botón <strong>Despertar servicio</strong> la "
            "levanta antes de la demo.",
        )
        estado = datos.salud(datos.api_actual())
        if estado:
            almacen = estado.get("almacen") or {}
            st.markdown("**Servicio al que está conectado este tablero**")
            st.json({
                "api": datos.api_actual(),
                "version": estado.get("version"),
                "modelo": estado.get("modelo"),
                "version_modelo": estado.get("version_modelo"),
                "umbral_decision": estado.get("umbral_decision"),
                "integridad_artefactos": estado.get("integridad_artefactos"),
                "almacen": almacen,
            })

    with tab_api:
        st.dataframe(
            pd.DataFrame(ENDPOINTS, columns=["método", "ruta", "para qué sirve"]),
            hide_index=True,
        )
        st.markdown("**Variables de entorno**")
        st.dataframe(
            pd.DataFrame(VARIABLES, columns=["variable", "efecto"]),
            hide_index=True,
        )
        estilos.bloque(
            "Los nombres de los endpoints no son negociables.",
            "/predict, /predict/batch y /history están fijados por el diseño del "
            "E14 y por los criterios FUN del proyecto. Un alias como /prediccion "
            "no existe y no se va a agregar.",
        )

    with tab_limites:
        st.markdown("**Qué significa cada cifra**")
        st.dataframe(
            pd.DataFrame([
                (
                    "Macro-F1",
                    (
                        "Media del F1 por clase sin ponderar por tamaño. Castiga al "
                        "modelo cuando ignora una clase rara."
                    ),
                ),
                (
                    "Recall de ataque",
                    (
                        "De todos los ataques reales, cuántos se detectaron. Es la "
                        "cifra que importa para seguridad."
                    ),
                ),
                (
                    "Precisión de ataque",
                    (
                        "De todas las alertas, cuántas eran ataque. Baja significa "
                        "falsos positivos."
                    ),
                ),
                (
                    "Umbral",
                    (
                        "Probabilidad a partir de la cual se declara ataque. Se calibró "
                        "sobre el holdout del entrenamiento: 0.41."
                    ),
                ),
                (
                    "KDDTest+",
                    (
                        "Conjunto de prueba con familias de ataque que no están en "
                        "entrenamiento. Es la prueba honesta."
                    ),
                ),
            ], columns=["término", "definición"]),
            hide_index=True,
        )

        estilos.bloque(
            "Lo que el sistema no hace.",
            "No inspecciona paquetes en tiempo real ni reemplaza un IDS: clasifica "
            "registros de conexión con 41 características. No detecta ataques de "
            "día cero por nombre; el Isolation Forest solo ordena rareza. Y las "
            "familias r2l y u2r se detectan mal, con los números a la vista en "
            "Modelo y métricas.",
            tono="aviso",
        )
        estilos.bloque(
            "Sobre el verde del título.",
            "Ningún control de este tablero es decorativo. Si un botón no puede "
            "hacer nada, no se dibuja: se explica por qué.",
        )
