"""Graficas del tablero en Altair.

Altair viene con Streamlit, así que no agrega dependencias al despliegue. Se
usa en lugar de `st.line_chart` y compania porque aqui hace falta controlar
colores, orden de categorias, ejes y anotaciones: el color es informacion (rojo
es ataque), no decoracion.

Regla de la casa: ninguna grafica se dibuja sin datos reales detras. Si no hay
filas, la vista llama a `estilos.bloque` y no llega hasta aqui.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

INK = "#10201c"
MUTED = "#57675f"
LINEA = "#e2ebe7"
VERDE = "#0a7a58"
VERDE_CLARO = "#8dc9b3"
ROJO = "#ac2a1c"
AMBAR = "#8a5a00"

# Un color por familia, en el orden del NSL-KDD. Nada de morado: el morado en un
# tablero de seguridad se confunde con un tercer estado que no existe.
COLOR_CLASE = {
    "normal": "#2f7d5f",
    "dos": "#ac2a1c",
    "probe": "#b06a00",
    "r2l": "#7a5230",
    "u2r": "#37525e",
}
ORDEN_CLASES = ["normal", "dos", "probe", "r2l", "u2r"]


def _tema(grafica: alt.Chart, alto: int = 240) -> alt.Chart:
    """Aplica el tema comun y fija la altura."""
    return (
        grafica.properties(height=alto)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            gridColor="#eef3f0",
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
            scale=alt.Scale(domain=["normal", "ataque"], range=["#2f7d5f", ROJO]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[
            alt.Tooltip(f"{columna}:T", title="Hora", format="%d/%m %H:%M"),
            alt.Tooltip("etiqueta:N", title="Etiqueta"),
            alt.Tooltip("predicciones:Q", title="Predicciones"),
        ],
    )
    return _tema(base.mark_area(opacity=0.9, line=False, interpolate="monotone"), 250)


def serie_probabilidad(df: pd.DataFrame, umbral: float | None = None) -> alt.Chart:
    """Linea de p(ataque) por prediccion, con la linea del umbral de decision."""
    datos = df.copy()
    datos["n"] = range(1, len(datos) + 1)
    linea = (
        alt.Chart(datos)
        .mark_line(color=VERDE, strokeWidth=1.6)
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
    arco = base.mark_arc(innerRadius=58, outerRadius=92, stroke="#ffffff", strokeWidth=2)
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


def barras_horizontales(df: pd.DataFrame, categoria: str, valor: str,
                        titulo: str = "", color: str = VERDE) -> alt.Chart:
    """Barras ordenadas de mayor a menor, para conteos por categoria."""
    base = alt.Chart(df).encode(
        y=alt.Y(f"{categoria}:N", title=None, sort="-x"),
        x=alt.X(f"{valor}:Q", title=titulo),
        tooltip=[alt.Tooltip(f"{categoria}:N", title="Categoría"),
                 alt.Tooltip(f"{valor}:Q", title=valor.title())],
    )
    return _tema(base.mark_bar(color=color, cornerRadiusTopRight=3,
                               cornerRadiusBottomRight=3), 34 * max(3, len(df)))


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
            scale=alt.Scale(domain=["Detección", "Clasificación"], range=[VERDE, ROJO]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[alt.Tooltip(f"{color_por}:N", title="Familia"),
                 alt.Tooltip("serie:N", title="Medida"),
                 alt.Tooltip("recall:Q", title="Recall", format=".4f")],
    )
    return _tema(base.mark_bar(size=18, cornerRadiusTopLeft=3, cornerRadiusTopRight=3), 240)


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
        color=alt.Color("n:Q", scale=alt.Scale(scheme="greens"), legend=None),
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
    puntos = base.mark_point(filled=True, size=110, color=VERDE, opacity=0.95).encode(
        size=alt.Size("filas_entrenamiento:Q", title="Filas", scale=alt.Scale(range=[80, 500]))
    )
    texto = base.mark_text(align="left", dx=10, fontSize=11, color=INK).encode(
        text=alt.Text("macro_f1_binario:Q", format=".4f")
    )
    return _tema(puntos + texto, 40 * max(3, len(df)))
