"""Vista 6: sistema, módulos y trazabilidad de criterios.

Esta vista ya no declara estados por escrito. Al abrirse (y al pulsar "Volver a
verificar") mide: /health, /metrics, /alertas/estado, un GET por endpoint de
lectura, la URL del tablero y la latencia real de /predict. Con eso,
`tablero.verificacion` decide cada indicador y la vista solo lo dibuja. Lo que no
se pudo medir aparece como "no verificado" con el motivo, nunca en verde.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from tablero import client, verificacion
from tablero.ui import datos, estilos

RAIZ = Path(__file__).resolve().parents[2]
ENDPOINTS = [
    ("GET", "/health", "estado, integridad de artefactos y umbral"),
    ("GET", "/metrics", "métricas del modelo publicadas tal como se midieron"),
    ("GET", "/history", "predicciones guardadas, con límite"),
    ("GET", "/history/resumen", "totales y composición por clase"),
    ("GET", "/alertas/estado", "enviadas, fallidas y en cola"),
    ("POST", "/predict", "una conexión de 41 características"),
    ("POST", "/predict/batch", "hasta 500 filas por petición"),
    ("POST", "/alertas/prueba", "mensaje de prueba al chat configurado"),
]
MUESTRAS_LATENCIA = 5
ESPERA_ARRANQUE = 45
CLAVE = "verificacion_sistema"
TONO = {verificacion.OPERANDO: "ok", verificacion.FALLA: "mal",
        verificacion.NO_VERIFICADO: "medio"}


def _ajustes() -> tuple[str, int]:
    """URL pública del tablero y número de muestras de latencia, editables."""
    with st.expander("Ajustes de la verificación", expanded=False):
        url = st.text_input(
            "URL pública del tablero",
            value=os.environ.get("REDCENTINELA_TABLERO_URL", "").strip(),
            key="tablero_url_verificacion",
            help="Vacía significa que DEPLOY-013 no se puede comprobar. En Streamlit "
                 "Cloud se define con la variable REDCENTINELA_TABLERO_URL.",
        )
        muestras = st.number_input(
            "Muestras de latencia de /predict", min_value=1, max_value=20,
            value=MUESTRAS_LATENCIA, step=1, key="muestras_latencia",
            help="Cada muestra escribe una fila normal en el historial de la API.",
        )
    return url.strip(), int(muestras)


def _medir(api: str, tablero_url: str, muestras: int) -> dict:
    """Toma todas las mediciones. Devuelve lo crudo y el veredicto."""
    datos.cliente(api)
    salud = None
    try:
        salud = client.salud()
    except client.ApiError:
        salud = None

    metricas = alertas = None
    if salud is not None:
        try:
            metricas = client.metricas()
        except client.ApiError:
            metricas = None
        try:
            alertas = client.alertas_estado()
        except client.ApiError:
            alertas = None

    endpoints = None
    if salud is not None:
        endpoints = [client.sondear(ruta) for metodo, ruta, _ in ENDPOINTS if metodo == "GET"]

    tablero = client.sondear_url(tablero_url) if tablero_url else None

    latencia = None
    if salud is not None and salud.get("modelos_disponibles") and muestras > 0:
        latencia = verificacion.medir_latencia(client.predecir, muestras=muestras)

    veredicto = verificacion.verificar(
        api_url=api,
        tablero_url=tablero_url or None,
        salud=salud,
        metricas=metricas,
        alertas=alertas,
        endpoints=endpoints,
        latencia=latencia,
        tablero=tablero,
        repositorio=verificacion.inspeccionar_datasets(RAIZ),
    )
    return {
        "salud": salud,
        "metricas": metricas,
        "alertas": alertas,
        "endpoints": endpoints,
        "latencia": latencia,
        "tablero": tablero,
        "veredicto": veredicto,
    }


def _medir_con_arranque(api: str, tablero_url: str, muestras: int) -> dict:
    """Mide; si la API no contesta y es pública, espera a que despierte."""
    with st.spinner("Midiendo el sistema..."):
        medicion = _medir(api, tablero_url, muestras)
    if medicion["salud"] is None and verificacion.es_url_publica(api):
        with st.spinner(
            "La API no responde. El plan gratuito duerme el servicio tras unos "
            f"minutos sin tráfico: se espera hasta {ESPERA_ARRANQUE} s."
        ):
            despierta, segundos = client.esperar_api(ESPERA_ARRANQUE)
        if despierta:
            with st.spinner("Despierta. Repitiendo la medición..."):
                medicion = _medir(api, tablero_url, muestras)
            medicion["arranque_s"] = segundos
    return medicion


def _fila_modulos(veredicto: dict) -> list[tuple]:
    return [
        (m["id"], m["nombre"], m["motivo"], TONO.get(m["estado"], "medio"))
        for m in veredicto["modulos"]
    ]


def _fila_criterios(veredicto: dict) -> list[dict]:
    return [
        {
            "Criterio": f"{c['id']}",
            "Exigencia": c["exigencia"],
            "Medido": c["medido"],
            "Veredicto": c["estado"],
            "Motivo": c["motivo"],
        }
        for c in veredicto["criterios"]
    ]


def render() -> None:
    api = datos.api_actual()
    datos.cliente(api)
    estilos.encabezado(
        "Sistema y trazabilidad",
        "Cada indicador de esta vista sale de una medición hecha ahora mismo contra "
        "la API y el despliegue. Lo que no se pudo medir aparece como no verificado, "
        "con el motivo.",
    )

    tablero_url, muestras = _ajustes()
    clave = f"{api}|{tablero_url}|{muestras}"
    guardado = st.session_state.get(CLAVE)
    if guardado is None or guardado.get("clave") != clave:
        guardado = _medir_con_arranque(api, tablero_url, muestras)
        guardado["clave"] = clave
        st.session_state[CLAVE] = guardado

    veredicto = guardado["veredicto"]
    salud = guardado["salud"]
    endpoints = guardado["endpoints"]

    izquierda, derecha = st.columns([1, 3], gap="large")
    with izquierda:
        if st.button("Volver a verificar", type="primary", icon=":material/refresh:",
                     width="stretch"):
            st.session_state.pop(CLAVE, None)
            st.rerun()
    with derecha:
        estilos.estado_servicio(salud)
        if guardado.get("arranque_s") is not None:
            estilos.fuente(
                f"El servicio estaba dormido y despertó en {guardado['arranque_s']:.1f} s."
            )

    if salud is None:
        estilos.bloque(
            "La API no responde.",
            "Ni /health ni el resto de la superficie contestaron con esta URL "
            f"(<span class='rc-mono'>{api}</span>). No se marca ninguna falla "
            "definitiva: los módulos quedan como no verificados hasta que el "
            "servicio conteste. Si es Render en plan gratuito, usa el botón "
            "<strong>Despertar servicio</strong> de la barra lateral y vuelve a "
            "verificar.",
            tono="atencion",
        )

    ok_get = sum(1 for r in (endpoints or []) if r.get("codigo") == 200)
    total_get = len(endpoints or [])
    macro = veredicto.get("macro_f1")
    estilos.banda(
        "Sistema medido",
        f"Última medición: {veredicto['momento']}. "
        f"{veredicto['total_modulos']} módulos y cinco criterios comprobados contra "
        f"{api}.",
        [
            (f"{veredicto['operando']}/{veredicto['total_modulos']}", "Módulos operando",
             "solo los que pasaron su comprobación"),
            (f"{ok_get}/{total_get}" if total_get else "sin datos", "Endpoints de lectura",
             "200 en esta medición"),
            ("íntegros" if (salud or {}).get("integridad_artefactos") else "sin verificar",
             "Artefactos", "SHA-256 contra el manifiesto"),
            (str(veredicto.get("umbral") or "sin datos"), "Umbral",
             "calibrado en holdout interno"),
            (f"{macro:.4f}" if macro is not None else "sin datos", "Macro-F1",
             "KDDTest+, meta 0.90"),
        ],
        tono="sano" if veredicto["operando"] == veredicto["total_modulos"] else "",
    )

    estilos.seccion("1", "Módulos del alcance", "M1 a M6, cada uno por su comprobación")
    estilos.modulos(_fila_modulos(veredicto))
    estilos.fuente(
        "M1 se comprueba sobre los CSV versionados; M2 y M3 sobre /health y los GET; "
        "M4 sobre la URL del tablero; M5 sobre /alertas/estado; M6 sobre la URL "
        "pública y la persistencia del almacén."
    )

    estilos.seccion("2", "Criterios y veredicto", "medido, no declarado")
    estilos.tabla(
        _fila_criterios(veredicto),
        ["Criterio", "Exigencia", "Medido", "Veredicto", "Motivo"],
        fuertes=("Criterio",),
    )
    estilos.fuente(
        "PERF-003 se compara contra la meta de 0.90 con el valor publicado en "
        "/metrics. PERF-006 sale de cronometrar /predict ahora mismo; el número de "
        "muestras se ajusta arriba y cada muestra escribe una fila normal en el "
        "historial."
    )

    estilos.seccion("3", "Superficie de la API", "ocho endpoints, contrato fijo")
    medidos = {r["ruta"]: r for r in (endpoints or [])}
    filas = []
    for metodo, ruta, desc in ENDPOINTS:
        r = medidos.get(ruta)
        if metodo == "POST":
            resultado = "no se sondea (escribe)"
        elif r is None:
            resultado = "sin verificar"
        elif r.get("codigo") is None:
            resultado = f"sin respuesta ({r.get('error')})"
        else:
            resultado = f"{r['codigo']} en {r['ms']:.0f} ms"
        filas.append({"Método": metodo, "Ruta": ruta, "Para qué sirve": desc,
                      "Medición": resultado})
    estilos.tabla(filas, ["Método", "Ruta", "Para qué sirve", "Medición"],
                  fuertes=("Ruta",))
    estilos.fuente(
        "Los POST no se disparan para comprobar: /predict escribe en el historial y "
        "/alertas/prueba envía un mensaje al chat."
    )

    estilos.seccion("4", "Lo que esta vista no puede medir",
                    "dicho antes de que lo pregunten")
    estilos.bloque(
        "Límites de la verificación automática.",
        "El video demo, el ensayo con el jurado y la decisión del profesor sobre "
        "PERF-003 no se pueden comprobar desde el código, así que no tienen indicador: "
        "quedan como pendientes del calendario. Lo que sí está medido y en verde arriba "
        "es lo que el sistema puede demostrar por sí solo.",
        tono="nota",
    )
