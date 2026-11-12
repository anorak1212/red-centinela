"""Vista 6: sistema, módulos y trazabilidad de criterios.

Un tablero de seguridad sin esta vista obliga al jurado a preguntar qué existe y
qué no. Aquí se declara: seis módulos, ocho endpoints y los criterios que el
proyecto se puso, con la cifra medida al lado y el veredicto sin adornos.
"""

from __future__ import annotations

import streamlit as st

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
        estilos.banda(
            "Sistema en operación",
            f"Servicio {estado.get('servicio', 'red-centinela')} versión "
            f"{estado.get('version', '?')}, modelos "
            f"{', '.join(estado.get('modelo') or []) or 'sin cargar'}.",
            [
                ("4/6", "Módulos operando", "M1 a M4; M5 y M6 parciales"),
                ("8", "Endpoints", "todos verificados en este entorno"),
                ("íntegros" if estado.get("integridad_artefactos") else "no verificados",
                 "Artefactos", "SHA-256 contra el manifiesto"),
                (str(estado.get("umbral_decision", "?")), "Umbral", "calibrado en holdout interno"),
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
          "Operando; PERF-003 no cumplido."), "medio"),
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
    estilos.tabla(
        [{"Método": m, "Ruta": r, "Para qué sirve": d} for m, r, d in ENDPOINTS],
        ["Método", "Ruta", "Para qué sirve"], fuertes=("Ruta",),
    )
    if estado is not None:
        st.caption(
            f"Comprobado ahora contra {api}: versión {estado.get('version')}, "
            f"{len(estado.get('modelo') or [])} modelos cargados, almacén "
            f"{((estado.get('almacen') or {}).get('motor'))}."
        )

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
