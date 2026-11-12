"""Hoja de estilos y piezas de interfaz del tablero.

Sin dependencias externas: solo `st.markdown` con CSS propio. La paleta es de
dos tonos más un rojo de severidad; el objetivo es que una captura del tablero
se lea en el video sin que nadie tenga que ampliar la pantalla.
"""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
:root {
  --rc-tinta: #12181f;
  --rc-gris: #5b6673;
  --rc-borde: #dfe4ea;
  --rc-fondo: #f6f7f9;
  --rc-acento: #0f5c4a;
  --rc-alerta: #b3261e;
}

.rc-titulo { margin: 0 0 .15rem 0; font-size: 1.55rem; font-weight: 700;
  letter-spacing: -.01em; color: var(--rc-tinta); }
.rc-sub { margin: 0 0 1.1rem 0; color: var(--rc-gris); font-size: .92rem; }

.rc-rejilla { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: .6rem; margin-bottom: 1rem; }
.rc-kpi { border: 1px solid var(--rc-borde); border-radius: 10px; padding: .7rem .85rem;
  background: #fff; }
.rc-kpi-etiqueta { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
  color: var(--rc-gris); font-weight: 600; }
.rc-kpi-valor { font-size: 1.5rem; font-weight: 700; color: var(--rc-tinta);
  font-variant-numeric: tabular-nums; line-height: 1.2; }
.rc-kpi-nota { font-size: .74rem; color: var(--rc-gris); }
.rc-kpi.alerta .rc-kpi-valor { color: var(--rc-alerta); }

.rc-pill { display: inline-block; padding: .16rem .55rem; border-radius: 999px;
  font-size: .74rem; font-weight: 600; border: 1px solid transparent; }
.rc-pill.ok { background: #e7f3ef; color: var(--rc-acento); border-color: #bfded4; }
.rc-pill.mal { background: #fbeae9; color: var(--rc-alerta); border-color: #f0c6c2; }
.rc-pill.neutra { background: #eef1f4; color: var(--rc-gris); border-color: var(--rc-borde); }

.rc-bloque { border: 1px solid var(--rc-borde); border-radius: 10px; padding: .8rem .95rem;
  background: #fff; margin-bottom: .8rem; }
.rc-bloque h4 { margin: 0 0 .35rem 0; font-size: .95rem; color: var(--rc-tinta); }
.rc-bloque p { margin: 0; color: var(--rc-gris); font-size: .85rem; }
.rc-mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .82rem; }

.rc-aviso { border-left: 3px solid var(--rc-alerta); background: #fdf3f2;
  padding: .6rem .8rem; border-radius: 0 8px 8px 0; color: #6b1a15; font-size: .86rem; }
.rc-nota { border-left: 3px solid var(--rc-borde); background: var(--rc-fondo);
  padding: .6rem .8rem; border-radius: 0 8px 8px 0; color: var(--rc-gris); font-size: .84rem; }

section[data-testid="stSidebar"] { border-right: 1px solid var(--rc-borde); }
div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
#MainMenu, footer { visibility: hidden; }
</style>
"""


def aplicar() -> None:
    """Inyecta el CSS una vez por rerun."""
    st.markdown(CSS, unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str = "") -> None:
    st.markdown(f'<p class="rc-titulo">{titulo}</p>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<p class="rc-sub">{subtitulo}</p>', unsafe_allow_html=True)


def kpis(items: list[tuple], alerta: tuple[int, ...] = ()) -> None:
    """Rejilla de tarjetas: (etiqueta, valor, nota[, es_alerta]).

    Una tarjeta se pinta en rojo si su tupla trae un cuarto valor verdadero o si
    su índice está en `alerta`. El rojo es severidad, no decoración.
    """
    piezas = []
    for i, item in enumerate(items):
        etiqueta, valor, nota = item[0], item[1], item[2]
        marcada = bool(item[3]) if len(item) > 3 else i in alerta
        clase = "rc-kpi alerta" if marcada else "rc-kpi"
        piezas.append(
            f'<div class="{clase}"><div class="rc-kpi-etiqueta">{etiqueta}</div>'
            f'<div class="rc-kpi-valor">{valor}</div>'
            f'<div class="rc-kpi-nota">{nota}</div></div>'
        )
    st.markdown(f'<div class="rc-rejilla">{"".join(piezas)}</div>', unsafe_allow_html=True)


def pill(texto: str, tono: str = "neutra") -> str:
    """Devuelve el HTML de una etiqueta de estado (no la dibuja)."""
    return f'<span class="rc-pill {tono}">{texto}</span>'


def estado_servicio(estado: dict | None) -> None:
    """Una línea con el estado real del servicio, sin adornos."""
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
    clase = "rc-aviso" if tono == "aviso" else "rc-nota"
    st.markdown(
        f'<div class="{clase}"><strong>{titulo}</strong> {texto}</div>',
        unsafe_allow_html=True,
    )
