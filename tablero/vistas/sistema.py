"""Vista 6: sistema, módulos y trazabilidad de criterios.

Un tablero de seguridad sin esta vista obliga al jurado a preguntar qué existe y
qué no. Aquí se declara: seis módulos, ocho endpoints y los criterios que el
proyecto se puso, con la cifra medida al lado y el veredicto sin adornos.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tablero import client
from tablero.ui import datos, estilos

ENDPOINTS = [
    ("GET", "/health", "estado, integridad de artefactos y umbral"),
    ("GET", "/metrics", "métricas del modelo publicadas tal como se midieron"),
    ("POST", "/predict", "una conexión de 41 características"),
    ("POST", "/predict/batch", "hasta 500 filas por petición"),
    ("GET", "/history", "predicciones guardadas, con límite"),
    ("GET", "/history/resumen", "totales y composición por clase"),
    ("GET", "/alertas/estado", "enviadas, fallidas y en cola"),
    ("POST", "/alertas/prueba", "mensaje de prueba al chat configurado"),
]


def render() -> None:
    api = datos.api_actual()
    estilos.encabezado(
        "Sistema y trazabilidad",
        "Qué está construido, qué está desplegado y qué criterio se cumple. "
        "Un criterio que no se cumple se muestra como no cumplido, con la cifra medida al lado.",
    )

    estado = datos.salud(api)
    metricas = datos.metricas(api) or {}
    binario = metricas.get("binario_kddtest") or {}
    latencia = metricas.get("latencia") or {}
    macro_f1 = binario.get("macro_f1")

    if estado is None:
        estilos.estado_servicio(None)
        estilos.bloque(
            "La API no responde.",
            "Esta vista mezcla lo declarado con lo verificado en /health. Sin servicio "
            "solo se puede leer la parte declarada, así que no se muestra a medias.",
            tono="aviso",
        )
    else:
        verificacion = st.session_state.get("verificacion_endpoints")
        if verificacion and verificacion.get("api") == api:
            ok_get = sum(1 for r in verificacion["filas"] if r["codigo"] == 200)
            cifra_endpoints = (f"{ok_get}/{len(verificacion['filas'])}",
                               "Endpoints GET", "200 en la última verificación")
        else:
            cifra_endpoints = ("8", "Endpoints", "declarados, verifícalos en la sección 3")
        disponibles = estado.get("modelos_disponibles", True)
        operando = 4 if disponibles else 3
        estilos.banda(
            "Sistema en operación",
            f"Servicio {estado.get('servicio', 'red-centinela')} versión "
            f"{estado.get('version', '?')}, modelos "
            f"{', '.join(estado.get('modelo') or []) or 'sin cargar'}.",
            [
                (f"{operando}/6", "Módulos operando",
                 "M1 a M4, con M5 y M6 parciales" if disponibles
                 else "M2 sin artefactos en este entorno"),
                cifra_endpoints,
                ("íntegros" if estado.get("integridad_artefactos") else "no verificados",
                 "Artefactos", "SHA-256 contra el manifiesto"),
                (str(estado.get("umbral_decision") or "sin datos"), "Umbral",
                 "calibrado en holdout interno"),
                (f"{float(macro_f1):.4f}" if macro_f1 is not None else "sin datos",
                 "Macro-F1", "KDDTest+"),
            ],
        )

    estilos.seccion("1", "Módulos del alcance", "M1 a M6, sin renombrar")
    estilos.modulos([
        ("M1", "Repositorio y EDA",
         "Repositorio Git, cuaderno de Colab y análisis del NSL-KDD. Operando.", "ok"),
        ("M2", "Motor de detección",
         ("Random Forest binario y multiclase más Isolation Forest, con manifiesto SHA-256. "
          + ("Operando, aunque PERF-003 no se cumple."
             if (estado or {}).get("modelos_disponibles", True)
             else "Artefactos .joblib ausentes en este entorno: la API no predice.")),
         "medio" if (estado or {}).get("modelos_disponibles", True) else "mal"),
        ("M3", "API REST",
         (f"FastAPI con ocho endpoints y almacén {((estado or {}).get('almacen') or {}).get('motor', 'SQLite')}. "
          "Operando en local."), "ok"),
        ("M4", "Tablero Streamlit",
         "Seis vistas que solo consumen HTTP: no cargan modelos ni abren la base. Operando.", "ok"),
        ("M5", "Alertas Telegram",
         ("Código completo con agrupación y reintentos. Sin token no hay envío que "
          "demostrar: no verificado."), "mal"),
        ("M6", "Despliegue y operación",
         ("Blueprint de Render y empaquetado listos. Sin cuentas ni URL pública: "
          "pendiente."), "mal"),
    ])

    estilos.seccion("2", "Criterios y veredicto", "medido, no declarado")
    filas = [
        {"Criterio": "Integridad de artefactos",
         "Exigencia": "los cinco .joblib coinciden con el manifiesto SHA-256",
         "Medido": "íntegros" if (estado or {}).get("integridad_artefactos") else "no verificados",
         "Veredicto": "cumplido" if (estado or {}).get("integridad_artefactos") else "no cumplido"},
        {"Criterio": "PERF-003 (macro-F1)",
         "Exigencia": "≥ 0.90 sobre KDDTest+",
         "Medido": f"{float(macro_f1):.4f}" if macro_f1 is not None else "sin datos",
         "Veredicto": "no cumplido" if (macro_f1 is None or float(macro_f1) < 0.90) else "cumplido"},
        {"Criterio": "Latencia por consulta",
         "Exigencia": "≤ 200 ms en el percentil 95",
         "Medido": f"{float(latencia.get('ms_por_fila_sola', 0)):.0f} ms por fila (desarrollo)",
         "Veredicto": "no cumplido en desarrollo"},
        {"Criterio": "ALERT-010 (aviso enviado)",
         "Exigencia": "mensaje confirmado en el chat de Telegram",
         "Medido": "sin token ni chat_id configurados",
         "Veredicto": "no evidenciado"},
        {"Criterio": "DEPLOY-013 (URL pública)",
         "Exigencia": "API y tablero accesibles sin instalar nada",
         "Medido": "solo 127.0.0.1:8000 y 127.0.0.1:8501",
         "Veredicto": "pendiente"},
    ]
    estilos.tabla(filas, ["Criterio", "Exigencia", "Medido", "Veredicto"], fuertes=("Criterio",))
    estilos.bloque(
        "Esto no se maquilla.",
        "Sobre KDDTest+ el macro-F1 es 0.7995 y la meta era 0.90. No es un error de "
        "implementación: KDDTest+ tiene familias de ataque que no existen en el "
        "entrenamiento y la literatura reporta valores cercanos a 0.80 en este conjunto. "
        "La solicitud de cambio está en docs/SOLICITUD_CAMBIO_PERF-003.md y espera "
        "decisión del profesor.",
    )

    estilos.seccion("3", "Superficie de la API", "ocho endpoints, contrato fijo")
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        verificacion = st.session_state.get("verificacion_endpoints")
        medidos = {}
        if verificacion and verificacion.get("api") == api:
            medidos = {r["ruta"]: r for r in verificacion["filas"]}
        filas = []
        for metodo, ruta, desc in ENDPOINTS:
            r = medidos.get(ruta)
            if metodo == "POST":
                resultado = "no se sondea (escribe)"
            elif r is None:
                resultado = "sin verificar"
            elif r["codigo"] is None:
                resultado = f"sin respuesta ({r['error']})"
            else:
                resultado = f"{r['codigo']} en {r['ms']:.0f} ms"
            filas.append({"Método": metodo, "Ruta": ruta, "Para qué sirve": desc,
                          "Verificación": resultado})
        estilos.tabla(filas, ["Método", "Ruta", "Para qué sirve", "Verificación"],
                      fuertes=("Ruta",))
    with derecha:
        st.markdown("**Verificación en vivo**")
        st.caption(
            "Hace un GET real a cada endpoint de lectura y mide el tiempo de respuesta. "
            "Los POST no se disparan: /predict escribiría en el historial y "
            "/alertas/prueba enviaría un mensaje."
        )
        if st.button("Verificar endpoints ahora", type="primary", key="btn_verificar_endpoints",
                     icon=":material/network_check:", disabled=estado is None):
            with st.spinner("Sondeando endpoints..."):
                resultados = [client.sondear(ruta) for metodo, ruta, _ in ENDPOINTS
                              if metodo == "GET"]
            st.session_state["verificacion_endpoints"] = {
                "api": api, "filas": resultados,
                "momento": pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S UTC"),
            }
            st.rerun()
        verificacion = st.session_state.get("verificacion_endpoints")
        if verificacion and verificacion.get("api") == api:
            ok_get = sum(1 for r in verificacion["filas"] if r["codigo"] == 200)
            tiempos = [r["ms"] for r in verificacion["filas"] if r["ms"] is not None]
            estilos.kpis([
                ("Respondieron 200", f"{ok_get}/{len(verificacion['filas'])}",
                 f"verificado a las {verificacion['momento']}", ok_get < len(verificacion["filas"])),
                ("Tiempo máximo", f"{max(tiempos):.0f} ms" if tiempos else "sin datos",
                 "el GET más lento"),
            ])
            no_ok = [r for r in verificacion["filas"] if r["codigo"] != 200]
            for r in no_ok:
                motivo = r["error"] or f"HTTP {r['codigo']}"
                if r["ruta"] == "/metrics" and r["codigo"] == 503:
                    motivo += " (falta metrics.json)"
                st.warning(f"{r['ruta']}: {motivo}")

    estilos.seccion("4", "Lo que falta para la defensa", "dicho antes de que lo pregunten")
    estilos.kpis([
        ("Despliegue", "pendiente", "sin cuentas de Render, Neon ni Streamlit Cloud", True),
        ("Alertas", "sin evidencia", "falta token y chat_id del bot", True),
        ("Video demo", "no grabado", "3 a 5 minutos, con la API en vivo", True),
        ("Ensayo", "no hecho", "recorrido completo con el jurado", True),
    ])
    st.caption(
        "Ninguna de estas cuatro se puede cerrar desde el código: dependen de cuentas, "
        "credenciales o del calendario. El producto, las pruebas y la documentación sí "
        "están cerrados y verificables en este repositorio."
    )
