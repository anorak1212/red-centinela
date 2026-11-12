"""Sistema visual del tablero Red Centinela.

Un solo acento (verde centinela), un solo radio, una sola escala tipografica.
Todo numero va en cifras tabulares para que las columnas se lean en vertical.
Nada de morado, nada de gradientes: la jerarquia la hacen el tamano y el aire.
"""

from __future__ import annotations

import html as _html

import streamlit as st

CSS = """
<style>
:root {
  --rc-ink: #10201c;
  --rc-ink-2: #24352f;
  --rc-muted: #57675f;
  --rc-line: #e2ebe7;
  --rc-line-2: #cfdcd5;
  --rc-paper: #ffffff;
  --rc-canvas: #f4f7f5;
  --rc-green: #0a7a58;
  --rc-green-dark: #07543d;
  --rc-wash: #ecf6f1;
  --rc-red: #ac2a1c;
  --rc-red-wash: #fdf1ee;
  --rc-amber: #8a5a00;
  --rc-radio: 10px;
  --rc-sombra: 0 1px 2px rgba(16, 32, 28, .05), 0 8px 22px rgba(16, 32, 28, .05);
}

html, body, [class*="css"] {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.stApp { background: var(--rc-canvas); color: var(--rc-ink); }
.block-container { max-width: 1440px; padding-top: 1.6rem; padding-bottom: 3.5rem; }
h1, h2, h3, h4 { color: var(--rc-ink); letter-spacing: -.02em; font-weight: 720; }
h2 { font-size: 1.32rem; margin: .2rem 0 .35rem; }
h3 { font-size: 1.04rem; margin: .2rem 0 .3rem; }
p, label, [data-testid="stCaptionContainer"] { color: var(--rc-muted); }
[data-testid="stCaptionContainer"] { font-size: .8rem; line-height: 1.5; }
hr { border-color: var(--rc-line); }

/* ---------- marca ---------- */
.rc-brand { padding: .2rem 0 1rem; }
.rc-brand-mark { display: flex; align-items: center; gap: .65rem; }
.rc-brand-icon { display: grid; place-items: center; width: 38px; height: 38px;
  border-radius: 11px; background: var(--rc-green-dark); color: #fff; font-size: 1.05rem; }
.rc-brand-name { color: var(--rc-ink); font-weight: 760; font-size: 1.02rem; letter-spacing: -.02em; }
.rc-brand-meta { color: var(--rc-muted); font-size: .7rem; margin: .3rem 0 0 2.9rem;
  letter-spacing: .08em; text-transform: uppercase; }

/* ---------- banda de portada ---------- */
.rc-banda { background: var(--rc-green-dark); border-radius: 14px; padding: 1.5rem 1.6rem 1.35rem;
  margin: 0 0 1.5rem; color: #fff; }
.rc-banda-eyebrow { font-size: .68rem; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: rgba(255, 255, 255, .66); margin: 0 0 .5rem; }
.rc-banda-titulo { margin: 0 0 .4rem; font-size: clamp(1.55rem, 2.2vw, 2.1rem); line-height: 1.1;
  font-weight: 760; letter-spacing: -.035em; color: #fff; }
.rc-banda-sub { margin: 0; max-width: 70ch; font-size: .9rem; line-height: 1.5;
  color: rgba(255, 255, 255, .8); }
.rc-banda-cifras { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1px; margin-top: 1.4rem; background: rgba(255, 255, 255, .16); border-radius: 8px; overflow: hidden; }
.rc-banda-cifra { background: var(--rc-green-dark); padding: .85rem 1rem .8rem; }
.rc-banda-valor { font-size: clamp(1.5rem, 2.4vw, 2.05rem); font-weight: 740; line-height: 1.05;
  color: #fff; font-variant-numeric: tabular-nums; letter-spacing: -.03em; }
.rc-banda-etiqueta { margin-top: .35rem; font-size: .7rem; letter-spacing: .1em; text-transform: uppercase;
  color: rgba(255, 255, 255, .7); font-weight: 650; }
.rc-banda-nota { margin-top: .2rem; font-size: .74rem; color: rgba(255, 255, 255, .55); }

/* ---------- encabezado de pagina ---------- */
.rc-eyebrow { color: var(--rc-green); font-size: .68rem; font-weight: 760;
  letter-spacing: .14em; text-transform: uppercase; margin: 0 0 .4rem; }
.rc-titulo { margin: 0 0 .3rem; font-size: clamp(1.6rem, 2.3vw, 2.15rem); line-height: 1.12;
  font-weight: 760; letter-spacing: -.035em; color: var(--rc-ink); }
.rc-sub { max-width: 82ch; margin: 0 0 1.3rem; color: var(--rc-muted);
  font-size: .92rem; line-height: 1.55; }

/* ---------- secciones numeradas ---------- */
.rc-seccion { display: flex; align-items: baseline; gap: .6rem; margin: 1.9rem 0 .15rem;
  padding-bottom: .5rem; border-bottom: 1px solid var(--rc-line); }
.rc-seccion-num { font-family: ui-monospace, Consolas, monospace; font-size: .72rem; font-weight: 700;
  color: var(--rc-green); letter-spacing: .04em; }
.rc-seccion-titulo { font-size: 1.06rem; font-weight: 740; color: var(--rc-ink); letter-spacing: -.015em; }
.rc-seccion-nota { margin-left: auto; font-size: .76rem; color: var(--rc-muted); text-align: right; }

/* ---------- tarjetas de indicador ---------- */
.rc-rejilla { display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: .75rem; margin: .9rem 0 1.1rem; }
.rc-kpi { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); padding: .85rem .95rem;
  background: var(--rc-paper); box-shadow: var(--rc-sombra); border-top: 2px solid var(--rc-green); }
.rc-kpi.alerta { border-top-color: var(--rc-red); }
.rc-kpi.neutra { border-top-color: var(--rc-line-2); }
.rc-kpi-etiqueta { font-size: .68rem; text-transform: uppercase; letter-spacing: .1em;
  color: var(--rc-muted); font-weight: 700; }
.rc-kpi-valor { margin-top: .38rem; font-size: clamp(1.35rem, 1.9vw, 1.75rem); font-weight: 740;
  color: var(--rc-ink); font-variant-numeric: tabular-nums; line-height: 1.1; letter-spacing: -.03em; }
.rc-kpi.alerta .rc-kpi-valor { color: var(--rc-red); }
.rc-kpi-nota { margin-top: .3rem; font-size: .74rem; color: var(--rc-muted); line-height: 1.4; }

/* ---------- barras de metrica ---------- */
.rc-met { margin: .55rem 0 .2rem; }
.rc-met-fila { display: flex; justify-content: space-between; align-items: baseline;
  font-size: .8rem; color: var(--rc-ink-2); margin-bottom: .22rem; }
.rc-met-nombre { font-weight: 620; letter-spacing: -.01em; }
.rc-met-cifra { font-variant-numeric: tabular-nums; color: var(--rc-muted); font-size: .78rem; }
.rc-met-pista { height: 6px; border-radius: 999px; background: #eaf0ed; overflow: hidden; }
.rc-met-relleno { height: 100%; border-radius: 999px; background: var(--rc-green); }
.rc-met-relleno.mal { background: var(--rc-red); }
.rc-met-relleno.medio { background: var(--rc-amber); }

/* ---------- tabla html ---------- */
.rc-tabla-envoltura { border: 1px solid var(--rc-line); border-radius: var(--rc-radio);
  background: var(--rc-paper); overflow: hidden; margin: .7rem 0 1rem; box-shadow: var(--rc-sombra); }
table.rc-tabla { width: 100%; border-collapse: collapse; font-size: .82rem; }
table.rc-tabla th { text-align: left; font-size: .66rem; text-transform: uppercase; letter-spacing: .1em;
  color: var(--rc-muted); font-weight: 700; padding: .6rem .8rem; background: #fbfdfc;
  border-bottom: 1px solid var(--rc-line); }
table.rc-tabla td { padding: .55rem .8rem; border-bottom: 1px solid #f1f5f3; color: var(--rc-ink-2);
  vertical-align: top; }
table.rc-tabla tr:last-child td { border-bottom: 0; }
table.rc-tabla td.num, table.rc-tabla th.num { text-align: right; font-variant-numeric: tabular-nums; }
table.rc-tabla td.fuerte { color: var(--rc-ink); font-weight: 640; }

/* ---------- modulos ---------- */
.rc-modulos { display: grid; grid-template-columns: repeat(auto-fit, minmax(228px, 1fr));
  gap: .7rem; margin: .8rem 0 1.1rem; }
.rc-modulo { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); padding: .8rem .9rem;
  background: var(--rc-paper); box-shadow: var(--rc-sombra); }
.rc-modulo-cab { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.rc-modulo-id { font-family: ui-monospace, Consolas, monospace; font-size: .72rem; font-weight: 700;
  color: var(--rc-green); }
.rc-modulo-nombre { margin-top: .3rem; font-size: .9rem; font-weight: 680; color: var(--rc-ink); }
.rc-modulo-texto { margin-top: .3rem; font-size: .76rem; line-height: 1.45; color: var(--rc-muted); }
.rc-punto { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.rc-punto.ok { background: var(--rc-green); }
.rc-punto.mal { background: var(--rc-red); }
.rc-punto.medio { background: var(--rc-amber); }

/* ---------- etiquetas y bloques ---------- */
.rc-pill { display: inline-flex; align-items: center; gap: .3rem; margin: 0 .28rem .32rem 0;
  padding: .26rem .6rem; border-radius: 999px; font-size: .71rem; font-weight: 660;
  border: 1px solid transparent; }
.rc-pill.ok { background: var(--rc-wash); color: var(--rc-green-dark); border-color: #cde7da; }
.rc-pill.mal { background: var(--rc-red-wash); color: var(--rc-red); border-color: #f2cec7; }
.rc-pill.neutra { background: #eef2f0; color: #4d5d57; border-color: var(--rc-line-2); }
.rc-bloque { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); padding: .8rem .95rem;
  background: var(--rc-paper); margin: .6rem 0 .9rem; }
.rc-bloque h4 { margin: 0 0 .3rem; font-size: .93rem; color: var(--rc-ink); }
.rc-bloque p { margin: 0; color: var(--rc-muted); font-size: .84rem; line-height: 1.5; }
.rc-mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .8rem; }
.rc-aviso { border: 1px solid #f2cec7; border-left: 3px solid var(--rc-red); background: var(--rc-red-wash);
  padding: .75rem .9rem; border-radius: 8px; color: #6d2018; font-size: .84rem; line-height: 1.5; }
.rc-nota { border: 1px solid var(--rc-line); border-left: 3px solid var(--rc-line-2); background: #fbfdfc;
  padding: .75rem .9rem; border-radius: 8px; color: #4d5d57; font-size: .84rem; line-height: 1.5; }
.rc-fuente { font-size: .72rem; color: var(--rc-muted); margin: .2rem 0 .9rem; }

/* ---------- medidor de probabilidad ---------- */
.rc-prob { margin: .2rem 0 1.1rem; }
.rc-prob-cab { display: flex; justify-content: space-between; align-items: baseline;
  font-size: .74rem; color: var(--rc-muted); margin-bottom: .3rem; }
.rc-prob-pista { position: relative; height: 10px; border-radius: 999px; background: #eaf0ed; }
.rc-prob-relleno { height: 100%; border-radius: 999px; background: var(--rc-green); }
.rc-prob-relleno.ataque { background: var(--rc-red); }
.rc-prob-marca { position: absolute; top: -4px; width: 2px; height: 18px; background: var(--rc-amber); }

/* ---------- controles nativos ---------- */
section[data-testid="stSidebar"] { background: #fbfdfc; border-right: 1px solid var(--rc-line); }
section[data-testid="stSidebar"] > div { padding-top: 1rem; }
button[kind="primary"], .stButton button[kind="primary"] { background: var(--rc-green-dark);
  border-color: var(--rc-green-dark); }
.stButton button, .stDownloadButton button { border-radius: 8px; font-weight: 620; }
.stButton button:hover, .stDownloadButton button:hover { border-color: var(--rc-green); color: var(--rc-green-dark); }
div[data-testid="stMetric"] { background: var(--rc-paper); border: 1px solid var(--rc-line);
  border-radius: var(--rc-radio); padding: .7rem .9rem; }
div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-size: 1.5rem; }
div[data-testid="stTabs"] button[role="tab"] { font-weight: 640; }
div[data-testid="stDataFrame"] { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); overflow: hidden; }
div[data-testid="stExpander"] { background: var(--rc-paper); border: 1px solid var(--rc-line); border-radius: var(--rc-radio); }
div[data-testid="stProgress"] > div > div > div > div { background: var(--rc-green); }
input, textarea, [data-baseweb="select"] > div { border-radius: 8px !important; }
#MainMenu, footer { visibility: hidden; }
@media (max-width: 760px) {
  .block-container { padding: 1rem .9rem 2rem; }
  .rc-banda { padding: 1.1rem 1.1rem 1rem; }
  .rc-rejilla { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; }
  .rc-kpi { padding: .7rem .75rem; }
  .rc-kpi-valor { font-size: 1.25rem; }
  .rc-seccion-nota { display: none; }
  table.rc-tabla { font-size: .76rem; }
}
</style>
"""


def aplicar() -> None:
    """Inyecta los estilos del producto."""
    st.markdown(CSS, unsafe_allow_html=True)


def _esc(valor: object) -> str:
    return _html.escape(str(valor), quote=False)


def encabezado(titulo: str, subtitulo: str = "", eyebrow: str = "Centro de operaciones") -> None:
    st.markdown(f'<p class="rc-eyebrow">{_esc(eyebrow)} · NSL-KDD</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="rc-titulo">{_esc(titulo)}</p>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<p class="rc-sub">{_esc(subtitulo)}</p>', unsafe_allow_html=True)


def banda(titulo: str, subtitulo: str, cifras: list[tuple]) -> None:
    """Portada de la vista: titulo y hasta cinco cifras grandes.

    Cada cifra es (valor, etiqueta, nota). La banda es lo unico oscuro de la
    pagina: sirve para que el estado del servicio se lea de pie, a dos metros
    del proyector, sin acercarse a la pantalla.
    """
    piezas = []
    for valor, etiqueta, nota in cifras:
        piezas.append(
            f'<div class="rc-banda-cifra"><div class="rc-banda-valor">{_esc(valor)}</div>'
            f'<div class="rc-banda-etiqueta">{_esc(etiqueta)}</div>'
            f'<div class="rc-banda-nota">{_esc(nota)}</div></div>'
        )
    st.markdown(
        '<div class="rc-banda">'
        '<p class="rc-banda-eyebrow">Centro de operaciones · NSL-KDD</p>'
        f'<p class="rc-banda-titulo">{_esc(titulo)}</p>'
        f'<p class="rc-banda-sub">{_esc(subtitulo)}</p>'
        f'<div class="rc-banda-cifras">{"".join(piezas)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def seccion(numero: str, titulo: str, nota: str = "") -> None:
    """Encabezado de seccion con numero y regla inferior."""
    cola = f'<span class="rc-seccion-nota">{_esc(nota)}</span>' if nota else ""
    st.markdown(
        f'<div class="rc-seccion"><span class="rc-seccion-num">{_esc(numero)}</span>'
        f'<span class="rc-seccion-titulo">{_esc(titulo)}</span>{cola}</div>',
        unsafe_allow_html=True,
    )


def kpis(items: list[tuple], alerta: tuple[int, ...] = ()) -> None:
    """Tarjetas de indicador: (etiqueta, valor, nota[, es_alerta])."""
    piezas = []
    for i, item in enumerate(items):
        etiqueta, valor, nota = item[0], item[1], item[2]
        marcada = bool(item[3]) if len(item) > 3 else i in alerta
        clase = "rc-kpi alerta" if marcada else "rc-kpi"
        piezas.append(
            f'<div class="{clase}"><div class="rc-kpi-etiqueta">{_esc(etiqueta)}</div>'
            f'<div class="rc-kpi-valor">{_esc(valor)}</div>'
            f'<div class="rc-kpi-nota">{_esc(nota)}</div></div>'
        )
    st.markdown(f'<div class="rc-rejilla">{"".join(piezas)}</div>', unsafe_allow_html=True)


def pill(texto: str, tono: str = "neutra") -> str:
    """Devuelve HTML de una etiqueta de estado."""
    return f'<span class="rc-pill {tono}">{_esc(texto)}</span>'


def barras(items: list[tuple], escala: float = 1.0) -> None:
    """Barras horizontales: (nombre, valor, texto, tono).

    Se usan para meter varias metricas en el ancho de una columna; una grafica
    por metrica seria ruido. El tono es 'ok', 'medio' o 'mal'.
    """
    piezas = []
    for nombre, valor, texto, tono in items:
        ancho = 0.0 if not escala else max(0.0, min(1.0, float(valor) / escala)) * 100
        piezas.append(
            f'<div class="rc-met"><div class="rc-met-fila">'
            f'<span class="rc-met-nombre">{_esc(nombre)}</span>'
            f'<span class="rc-met-cifra">{_esc(texto)}</span></div>'
            f'<div class="rc-met-pista"><div class="rc-met-relleno {tono}" '
            f'style="width:{ancho:.1f}%"></div></div></div>'
        )
    st.markdown("".join(piezas), unsafe_allow_html=True)


def tabla(filas: list[dict], columnas: list[str], numericas: tuple[str, ...] = (),
          fuertes: tuple[str, ...] = ()) -> None:
    """Tabla HTML compacta. `filas` ya viene con las llaves de `columnas`."""
    cabecera = "".join(
        f'<th class="{"num" if (c in numericas) else ""}">{_esc(c)}</th>' for c in columnas
    )
    cuerpo = []
    for fila in filas:
        celdas = []
        for c in columnas:
            clase = "num" if c in numericas else ("fuerte" if c in fuertes else "")
            celdas.append(f'<td class="{clase}">{_esc(fila.get(c, ""))}</td>')
        cuerpo.append(f"<tr>{''.join(celdas)}</tr>")
    st.markdown(
        f'<div class="rc-tabla-envoltura"><table class="rc-tabla"><thead><tr>{cabecera}</tr>'
        f"</thead><tbody>{''.join(cuerpo)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def modulos(items: list[tuple]) -> None:
    """Tablero de modulos: (id, nombre, texto, estado) con estado ok/medio/mal."""
    piezas = []
    for ident, nombre, texto, estado in items:
        color = {"ok": "ok", "medio": "medio"}.get(estado, "mal")
        piezas.append(
            f'<div class="rc-modulo"><div class="rc-modulo-cab">'
            f'<span class="rc-modulo-id">{_esc(ident)}</span>'
            f'<span class="rc-punto {color}"></span></div>'
            f'<div class="rc-modulo-nombre">{_esc(nombre)}</div>'
            f'<div class="rc-modulo-texto">{_esc(texto)}</div></div>'
        )
    st.markdown(f'<div class="rc-modulos">{"".join(piezas)}</div>', unsafe_allow_html=True)


def fuente(texto: str) -> None:
    """Linea de procedencia bajo una grafica o tabla."""
    st.markdown(f'<p class="rc-fuente">{_esc(texto)}</p>', unsafe_allow_html=True)


def progress_probabilidad(probabilidad: float, umbral: float) -> None:
    """Medidor de p(ataque) con la marca del umbral de decision.

    Se dibuja a mano en vez de con `st.progress` porque la marca del umbral es
    la informacion: sin ella, un 0.42 y un 0.98 se leen igual de "altos".
    """
    p = max(0.0, min(1.0, float(probabilidad)))
    u = max(0.0, min(1.0, float(umbral)))
    clase = "rc-prob-relleno ataque" if p >= u else "rc-prob-relleno"
    st.markdown(
        '<div class="rc-prob">'
        f'<div class="rc-prob-cab"><span>p(ataque) = {p:.4f}</span>'
        f'<span>umbral = {u:.2f}</span></div>'
        f'<div class="rc-prob-pista"><div class="{clase}" style="width:{p * 100:.1f}%"></div>'
        f'<div class="rc-prob-marca" style="left:calc({u * 100:.1f}% - 1px)"></div></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def estado_servicio(estado: dict | None) -> None:
    """Muestra la salud real de la API."""
    if not estado:
        st.markdown(pill("API sin respuesta", "mal"), unsafe_allow_html=True)
        return
    integridad = "artefactos íntegros" if estado.get("integridad_artefactos") else "artefactos NO verificados"
    almacen = (estado.get("almacen") or {}).get("motor", "?")
    persistente = (estado.get("almacen") or {}).get("persistente")
    piezas = [
        pill(f"v{estado.get('version', '?')}", "neutra"),
        pill(integridad, "ok" if estado.get("integridad_artefactos") else "mal"),
        pill(f"umbral {estado.get('umbral_decision', '?')}", "neutra"),
        pill(f"almacén {almacen}{'' if persistente else ' (no persiste)'}",
             "ok" if persistente else "neutra"),
    ]
    st.markdown(" ".join(piezas), unsafe_allow_html=True)


def bloque(titulo: str, texto: str, tono: str = "nota") -> None:
    """Panel compacto para avisos o explicaciones."""
    clase = "rc-aviso" if tono == "aviso" else "rc-nota"
    st.markdown(f'<div class="{clase}"><strong>{titulo}</strong> {texto}</div>',
                unsafe_allow_html=True)
