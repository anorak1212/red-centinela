"""Graficas del tablero en Altair.

Altair viene con Streamlit, así que no agrega dependencias al despliegue. Se
usa en lugar de `st.line_chart` y compania porque aqui hace falta controlar
colores, orden de categorias, ejes y anotaciones: el color es informacion (rojo
es ataque), no decoracion.

Regla de la casa: ninguna grafica se dibuja sin datos reales detras. Si no hay
filas, la vista llama a `estilos.bloque` y no llega hasta aqui.
"""

from __future__ import annotations

import functools

import altair as alt
import pandas as pd

from tablero.ui import preferencias

INK = "#0d1626"
MUTED = "#5a6578"
LINEA = "#e2e7ef"
MARCA = "#2450d6"
MARCA_CLARO = "#9db4f2"
NORMAL = "#13866f"
ROJO = "#cf3a2a"
AMBAR = "#b26b00"
# Alias conservados para las vistas que ya los importan.
VERDE = MARCA
VERDE_CLARO = MARCA_CLARO

# Un color por familia, en el orden del NSL-KDD. Normal usa el verde azulado de
# "sano"; las cuatro familias de ataque van del rojo al pizarra, de más a menos
# frecuente, para que el azul de la marca nunca se lea como una clase.
COLOR_CLASE = {
    "normal": NORMAL,
    "dos": ROJO,
    "probe": "#e08a1e",
    "r2l": "#9b4d2e",
    "u2r": "#4a5b78",
}
ORDEN_CLASES = ["normal", "dos", "probe", "r2l", "u2r"]
GRID = "#edf0f5"
PISTA = "#e8ecf3"
PAPEL = "#ffffff"
FUENTE = "Geist, system-ui, sans-serif"


def _actualizar_paleta() -> None:
    """Ajusta los colores del módulo al tema y al acento de la sesión.

    Las gráficas se construyen en cada ejecución del script, así que basta con
    fijar la paleta justo antes de armar cada una.
    """
    global INK, MUTED, LINEA, MARCA, MARCA_CLARO, NORMAL, ROJO, AMBAR
    global VERDE, VERDE_CLARO, GRID, PISTA, PAPEL
    principal, _, _, claro = preferencias.acento()
    MARCA, MARCA_CLARO = principal, claro
    if preferencias.oscuro():
        INK, MUTED, LINEA, GRID, PISTA, PAPEL = (
            "#e8edf6", "#93a0b5", "#33415e", "#1f2a40", "#222d44", "#121a2b")
        NORMAL, ROJO, AMBAR = "#2fbf9b", "#ff6b57", "#f0a72f"
    else:
        INK, MUTED, LINEA, GRID, PISTA, PAPEL = (
            "#0d1626", "#5a6578", "#e2e7ef", "#edf0f5", "#e8ecf3", "#ffffff")
        NORMAL, ROJO, AMBAR = "#13866f", "#cf3a2a", "#b26b00"
    VERDE, VERDE_CLARO = MARCA, MARCA_CLARO
    COLOR_CLASE.update({"normal": NORMAL, "dos": ROJO})


def _con_paleta(funcion):
    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        _actualizar_paleta()
        return funcion(*args, **kwargs)
    return envoltura


def _tema(grafica: alt.Chart, alto: int = 240) -> alt.Chart:
    """Aplica el tema comun y fija la altura."""
    return (
        grafica.properties(height=alto)
        .configure(background="transparent", font=FUENTE)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            gridColor=GRID,
            domainColor=LINEA,
            tickColor=LINEA,
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
            labelPadding=6,
            titlePadding=8,
        )
        .configure_legend(
            labelColor=MUTED,
            titleColor=MUTED,
            symbolType="square",
            labelFontSize=11,
            titleFontSize=11,
            orient="bottom",
            direction="horizontal",
        )
    )


@_con_paleta
def actividad(df: pd.DataFrame, columna: str = "momento") -> alt.Chart:
    """Area apilada de predicciones por hora, separando normales de ataques.

    `df` necesita `hora` (timestamp) y `etiqueta` ('normal' o 'ataque').
    """
    conteo = (
        df.groupby([pd.Grouper(key=columna, freq="h"), "etiqueta"], observed=True)
        .size()
        .reset_index(name="predicciones")
    )
    conteo["etiqueta"] = pd.Categorical(conteo["etiqueta"], ["normal", "ataque"], ordered=True)
    base = alt.Chart(conteo).encode(
        x=alt.X(f"{columna}:T", title=None, axis=alt.Axis(format="%H:%M", labelAngle=0)),
        y=alt.Y("predicciones:Q", title="Predicciones por hora", stack="zero"),
        color=alt.Color(
            "etiqueta:N",
            scale=alt.Scale(domain=["normal", "ataque"], range=[NORMAL, ROJO]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[
            alt.Tooltip(f"{columna}:T", title="Hora", format="%d/%m %H:%M"),
            alt.Tooltip("etiqueta:N", title="Etiqueta"),
            alt.Tooltip("predicciones:Q", title="Predicciones"),
        ],
    )
    return _tema(base.mark_area(opacity=0.9, line=False, interpolate="monotone"), 250)


@_con_paleta
def serie_probabilidad(df: pd.DataFrame, umbral: float | None = None) -> alt.Chart:
    """Linea de p(ataque) por prediccion, con la linea del umbral de decision."""
    datos = df.copy()
    datos["n"] = range(1, len(datos) + 1)
    linea = (
        alt.Chart(datos)
        .mark_line(color=MARCA, strokeWidth=1.6)
        .encode(
            x=alt.X("n:Q", title="Predicciones en orden de llegada"),
            y=alt.Y("probabilidad_ataque:Q", title="p(ataque)", scale=alt.Scale(domain=[0, 1])),
            tooltip=[
                alt.Tooltip("id:Q", title="ID"),
                alt.Tooltip("clase:N", title="Clase"),
                alt.Tooltip("probabilidad_ataque:Q", title="p(ataque)", format=".4f"),
            ],
        )
    )
    puntos = (
        alt.Chart(datos[datos["es_ataque"]])
        .mark_circle(color=ROJO, size=26, opacity=0.85)
        .encode(
            x="n:Q",
            y="probabilidad_ataque:Q",
            tooltip=[alt.Tooltip("id:Q", title="ID"), alt.Tooltip("clase:N", title="Clase")],
        )
    )
    capas = linea + puntos
    if umbral is not None:
        regla = (
            alt.Chart(pd.DataFrame({"u": [float(umbral)]}))
            .mark_rule(color=AMBAR, strokeDash=[4, 3], strokeWidth=1.2)
            .encode(y="u:Q")
        )
        etiqueta = (
            alt.Chart(pd.DataFrame({"u": [float(umbral)], "t": [f"umbral {umbral}"]}))
            .mark_text(align="left", dx=4, dy=-6, color=AMBAR, fontSize=10)
            .encode(y="u:Q", text="t:N")
        )
        capas = capas + regla + etiqueta
    return _tema(capas, 240)


@_con_paleta
def dona(df: pd.DataFrame, categoria: str = "clase", valor: str = "registros") -> alt.Chart:
    """Dona de composicion por clase, con el color de cada familia."""
    base = alt.Chart(df).encode(
        theta=alt.Theta(f"{valor}:Q", stack=True),
        color=alt.Color(
            f"{categoria}:N",
            scale=alt.Scale(domain=ORDEN_CLASES, range=[COLOR_CLASE[c] for c in ORDEN_CLASES]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[alt.Tooltip(f"{categoria}:N", title="Clase"),
                 alt.Tooltip(f"{valor}:Q", title="Registros")],
    )
    arco = base.mark_arc(innerRadius=58, outerRadius=92, stroke=PAPEL, strokeWidth=2)
    total = int(df[valor].sum()) if len(df) else 0
    centro = (
        alt.Chart(pd.DataFrame({"t": [f"{total:,}"], "s": ["predicciones"]}))
        .mark_text(fontSize=20, fontWeight=700, color=INK, dy=-6)
        .encode(text="t:N")
        + alt.Chart(pd.DataFrame({"s": ["predicciones"]}))
        .mark_text(fontSize=11, color=MUTED, dy=14)
        .encode(text="s:N")
    )
    return _tema(arco + centro, 220)


@_con_paleta
def barras_horizontales(df: pd.DataFrame, categoria: str, valor: str,
                        titulo: str = "", color: str | None = None) -> alt.Chart:
    """Barras ordenadas de mayor a menor, para conteos por categoria."""
    base = alt.Chart(df).encode(
        y=alt.Y(f"{categoria}:N", title=None, sort="-x"),
        x=alt.X(f"{valor}:Q", title=titulo),
        tooltip=[alt.Tooltip(f"{categoria}:N", title="Categoría"),
                 alt.Tooltip(f"{valor}:Q", title=valor.title())],
    )
    color = MARCA_CLARO if color == "claro" else (color or MARCA)
    return _tema(base.mark_bar(color=color, cornerRadiusTopRight=3,
                               cornerRadiusBottomRight=3), 34 * max(3, len(df)))


@_con_paleta
def valores_por_categoria(df: pd.DataFrame, color_por: str = "familia") -> alt.Chart:
    """Barras agrupadas deteccion contra clasificacion por familia.

    `df` va en formato largo: familia, serie ('Detección' o 'Clasificación'),
    recall. Se agrupan por familia para que la diferencia entre detectar y
    acertar la familia se vea de un golpe.
    """
    base = alt.Chart(df).encode(
        x=alt.X(f"{color_por}:N", title=None, sort=ORDEN_CLASES),
        xOffset=alt.XOffset("serie:N", sort=["Detección", "Clasificación"]),
        y=alt.Y("recall:Q", title="Recall", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color(
            "serie:N",
            scale=alt.Scale(domain=["Detección", "Clasificación"], range=[MARCA, ROJO]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[alt.Tooltip(f"{color_por}:N", title="Familia"),
                 alt.Tooltip("serie:N", title="Medida"),
                 alt.Tooltip("recall:Q", title="Recall", format=".4f")],
    )
    return _tema(base.mark_bar(size=18, cornerRadiusTopLeft=3, cornerRadiusTopRight=3), 240)


@_con_paleta
def matriz_confusion(matriz: list[list[int]], etiquetas: list[str]) -> alt.Chart:
    """Mapa de calor de la matriz de confusion, con el conteo escrito encima."""
    filas = []
    for i, real in enumerate(etiquetas):
        for j, predicho in enumerate(etiquetas):
            filas.append({"real": real, "predicho": predicho,
                          "n": int(matriz[i][j])})
    df = pd.DataFrame(filas)
    base = alt.Chart(df).encode(
        x=alt.X("predicho:N", title="Predicho", sort=etiquetas),
        y=alt.Y("real:N", title="Real", sort=etiquetas),
    )
    celdas = base.mark_rect().encode(
        color=alt.Color("n:Q", scale=alt.Scale(range=[PISTA, MARCA]), legend=None),
        tooltip=[alt.Tooltip("real:N", title="Real"),
                 alt.Tooltip("predicho:N", title="Predicho"),
                 alt.Tooltip("n:Q", title="Filas")],
    )
    texto = base.mark_text(fontSize=12).encode(
        text="n:Q",
        color=alt.condition(alt.datum.n > df["n"].max() * 0.55,
                            alt.value("#ffffff"), alt.value(INK)),
    )
    alto = 46 * len(etiquetas) + 30
    return _tema(celdas + texto, alto)


@_con_paleta
def comparativa(df: pd.DataFrame) -> alt.Chart:
    """Macro-F1 por modelo. El tamaño del punto indica filas de entrenamiento."""
    base = alt.Chart(df).encode(
        x=alt.X("macro_f1_binario:Q", title="Macro-F1 binario",
                scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("modelo:N", title=None, sort="x"),
        tooltip=[
            alt.Tooltip("modelo:N", title="Modelo"),
            alt.Tooltip("macro_f1_binario:Q", title="Macro-F1", format=".4f"),
            alt.Tooltip("filas_entrenamiento:Q", title="Filas de entrenamiento"),
            alt.Tooltip("nota:N", title="Nota"),
        ],
    )
    puntos = base.mark_point(filled=True, size=110, color=MARCA, opacity=0.95).encode(
        size=alt.Size("filas_entrenamiento:Q", title="Filas", scale=alt.Scale(range=[80, 500]))
    )
    texto = base.mark_text(align="left", dx=10, fontSize=11, color=INK).encode(
        text=alt.Text("macro_f1_binario:Q", format=".4f")
    )
    return _tema(puntos + texto, 40 * max(3, len(df)))


@_con_paleta
def histograma_probabilidad(df: pd.DataFrame, umbral: float | None,
                            umbral_simulado: float | None = None) -> alt.Chart:
    """Histograma de p(ataque) con el umbral real y, si se da, el simulado."""
    datos = df[["probabilidad_ataque", "etiqueta"]].copy()
    base = alt.Chart(datos).mark_bar(opacity=0.9, binSpacing=1).encode(
        x=alt.X("probabilidad_ataque:Q", bin=alt.Bin(maxbins=25, extent=[0, 1]),
                title="p(ataque)"),
        y=alt.Y("count():Q", title="Predicciones", stack="zero"),
        color=alt.Color("etiqueta:N",
                        scale=alt.Scale(domain=["normal", "ataque"], range=[NORMAL, ROJO]),
                        legend=alt.Legend(title="Decisión de la API")),
        tooltip=[alt.Tooltip("count():Q", title="Predicciones"),
                 alt.Tooltip("etiqueta:N", title="Decisión")],
    )
    capas = base
    reglas = []
    if umbral is not None:
        reglas.append({"u": float(umbral), "t": f"umbral API {float(umbral):.2f}", "c": AMBAR})
    if umbral_simulado is not None:
        reglas.append({"u": float(umbral_simulado),
                       "t": f"simulado {float(umbral_simulado):.2f}", "c": MARCA})
    for r in reglas:
        marco = pd.DataFrame([r])
        capas = capas + alt.Chart(marco).mark_rule(
            color=r["c"], strokeDash=[4, 3], strokeWidth=1.6).encode(x="u:Q")
        capas = capas + alt.Chart(marco).mark_text(
            align="left", dx=4, dy=-90, color=r["c"], fontSize=10).encode(x="u:Q", text="t:N")
    return _tema(capas, 220)


@_con_paleta
def medidor(valor: float, titulo: str, meta: float | None = None) -> alt.Chart:
    """Medidor semicircular 0-1 con el valor escrito en el centro.

    El color dice si llega a la meta (verde azulado), si está cerca (ámbar) o
    lejos (rojo). Sin meta, se pinta con el azul de la marca.
    """
    import math

    v = max(0.0, min(1.0, float(valor)))
    if meta is None:
        color = MARCA
    elif v >= meta:
        color = NORMAL
    elif v >= meta - 0.1:
        color = AMBAR
    else:
        color = ROJO
    datos = pd.DataFrame({"parte": ["valor", "resto"], "v": [v, 1 - v], "orden": [0, 1]})
    arco = alt.Chart(datos).mark_arc(innerRadius=50, outerRadius=68, cornerRadius=3).encode(
        theta=alt.Theta("v:Q", stack=True, scale=alt.Scale(range=[-math.pi / 2, math.pi / 2])),
        color=alt.Color("parte:N", scale=alt.Scale(domain=["valor", "resto"],
                                                   range=[color, PISTA]), legend=None),
        order=alt.Order("orden:Q"),
        tooltip=[alt.Tooltip("v:Q", title=titulo, format=".4f")],
    )
    pie = f"meta {meta:.2f}" if meta is not None else "sin meta fijada"
    # El centro del arco se fija en píxeles (y=86) para que el semicírculo
    # quede completo en 120 px de alto y el texto debajo del valor.
    capas = (
        arco.encode(y=alt.value(86))
        + alt.Chart(pd.DataFrame({"t": [f"{v:.3f}"]})).mark_text(
            fontSize=22, fontWeight=600, color=INK, baseline="bottom").encode(
            text="t:N", y=alt.value(84))
        + alt.Chart(pd.DataFrame({"t": [pie]})).mark_text(
            fontSize=10, color=MUTED, baseline="top").encode(text="t:N", y=alt.value(92))
    )
    return (capas.properties(height=120)
            .configure(background="transparent", font=FUENTE).configure_view(strokeWidth=0))


@_con_paleta
def embudo(df: pd.DataFrame) -> alt.Chart:
    """Embudo horizontal: etapa, filas y porcentaje sobre la primera etapa."""
    orden = df["etapa"].tolist()
    base = alt.Chart(df).encode(
        y=alt.Y("etapa:N", sort=orden, title=None,
                axis=alt.Axis(labelLimit=220, labelFontSize=11)),
        x=alt.X("filas:Q", title=None, axis=None),
        tooltip=[alt.Tooltip("etapa:N", title="Etapa"),
                 alt.Tooltip("filas:Q", title="Filas", format=","),
                 alt.Tooltip("pct:Q", title="Sobre ataques reales", format=".1%")],
    )
    barras = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=26).encode(
        color=alt.Color("etapa:N", sort=orden, legend=None,
                        scale=alt.Scale(range=[MARCA_CLARO, MARCA, NORMAL])),
    )
    texto = base.mark_text(align="left", dx=6, fontSize=11, color=INK).encode(
        text=alt.Text("rotulo:N"))
    return _tema(barras + texto, 150)


@_con_paleta
def f1_clases(df: pd.DataFrame) -> alt.Chart:
    """F1 por clase con el color de cada familia y la línea de 0.90."""
    base = alt.Chart(df).encode(
        x=alt.X("clase:N", sort=ORDEN_CLASES, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("f1:Q", title="F1", scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip("clase:N", title="Clase"),
                 alt.Tooltip("f1:Q", title="F1", format=".4f"),
                 alt.Tooltip("soporte:Q", title="Filas reales", format=",")],
    )
    barras = base.mark_bar(size=34, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        color=alt.Color("clase:N", legend=None, scale=alt.Scale(
            domain=ORDEN_CLASES, range=[COLOR_CLASE[c] for c in ORDEN_CLASES])))
    texto = base.mark_text(dy=-8, fontSize=11, color=INK).encode(text=alt.Text("f1:Q", format=".2f"))
    meta = alt.Chart(pd.DataFrame({"y": [0.9]})).mark_rule(
        color=AMBAR, strokeDash=[4, 3]).encode(y="y:Q")
    return _tema(barras + texto + meta, 230)


@_con_paleta
def generalizacion(df: pd.DataFrame) -> alt.Chart:
    """Macro-F1 binario por conjunto: de lo fácil (holdout) a lo difícil."""
    orden = df["conjunto"].tolist()
    base = alt.Chart(df).encode(
        x=alt.X("conjunto:N", sort=orden, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("macro_f1:Q", title="Macro-F1 binario", scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip("conjunto:N", title="Conjunto"),
                 alt.Tooltip("macro_f1:Q", title="Macro-F1", format=".4f"),
                 alt.Tooltip("nota:N", title="Nota")],
    )
    barras = base.mark_bar(size=46, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        color=alt.Color("conjunto:N", sort=orden, legend=None,
                        scale=alt.Scale(range=[MARCA_CLARO, MARCA, ROJO])))
    texto = base.mark_text(dy=-8, fontSize=11, color=INK).encode(
        text=alt.Text("macro_f1:Q", format=".3f"))
    regla = alt.Chart(pd.DataFrame({"y": [0.9]})).mark_rule(
        color=AMBAR, strokeDash=[4, 3]).encode(y="y:Q")
    return _tema(barras + texto + regla, 230)
