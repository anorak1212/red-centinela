"""Sistema visual del tablero Red Centinela.

Paleta "azul nocturno": la marca es azul centinela, y los estados tienen su
propio color semántico, separado de la marca, para que nunca se confundan:

- verde azulado = cumplido / tráfico normal / sano
- ámbar         = umbral, atención, parcial
- rojo          = ataque / incumplido / fallo

Un solo radio, una sola escala tipográfica (Geist y Geist Mono) y cifras
tabulares en todo número para que las columnas se lean en vertical. El acento,
el tema claro u oscuro, la densidad y las animaciones salen de las
preferencias de la sesión (vista Configuración).
"""

from __future__ import annotations

import html as _html

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

:root {
  --rc-ink: #0d1626;
  --rc-ink-2: #1f2b40;
  --rc-muted: #5a6578;
  --rc-line: #e2e7ef;
  --rc-line-2: #cbd3df;
  --rc-paper: #ffffff;
  --rc-canvas: #f3f5f9;
  --rc-marca: #2450d6;
  --rc-marca-osc: #1a3db0;
  --rc-noche: #0f1d3d;
  --rc-noche-2: #172a55;
  --rc-cian: #38c6d9;
  --rc-wash: #ebf0fe;
  --rc-ok: #13866f;
  --rc-ok-wash: #e7f6f2;
  --rc-red: #cf3a2a;
  --rc-red-wash: #fdf0ee;
  --rc-amber: #b26b00;
  --rc-amber-wash: #fdf5e6;
  --rc-paper-2: #f8f9fc;
  --rc-hover: #eef1f6;
  --rc-hover-suave: #fafbfe;
  --rc-pista: #e8ecf3;
  --rc-campo: #eef1f7;
  --rc-ok-txt: #0d6655;
  --rc-amber-txt: #8a5300;
  --rc-red-txt: #6f2117;
  --rc-neutra-txt: #4a5568;
  --rc-ok-borde: #c4e7dd;
  --rc-red-borde: #f4ccc6;
  --rc-amber-borde: #f1dcb4;
  --rc-marca-borde: #cdd9fb;
  --rc-cielo: #0ea5e9;
  --rc-indigo: #6366f1;
  --rc-rosa: #db2777;
  --rc-radio: 10px;
  --rc-sombra: 0 1px 2px rgba(13, 22, 38, .05), 0 8px 24px rgba(13, 22, 38, .05);
  --rc-sans: "Geist", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --rc-monof: "Geist Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
}

.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp input, .stApp textarea, .stApp button, .stApp table { font-family: var(--rc-sans); }
.stApp { background: var(--rc-canvas); color: var(--rc-ink); }
.block-container { max-width: 1400px; padding-top: 1.4rem; padding-bottom: 3rem; }
h1, h2, h3, h4 { color: var(--rc-ink); letter-spacing: -.015em; font-weight: 650; }
h2 { font-size: 1.3rem; margin: .2rem 0 .35rem; }
h3 { font-size: 1.02rem; margin: .2rem 0 .3rem; }
p, label, [data-testid="stCaptionContainer"] { color: var(--rc-muted); }
[data-testid="stCaptionContainer"] { font-size: .8rem; line-height: 1.5; }
hr { border-color: var(--rc-line); }
code { font-family: var(--rc-monof); color: var(--rc-marca-osc); background: var(--rc-wash); }

/* ---------- marca ---------- */
.rc-brand { padding: 0 2rem .6rem 0; }
.rc-brand-mark { display: flex; align-items: center; gap: .7rem; }
.rc-brand-icon { display: grid; place-items: center; width: 40px; height: 40px; flex: none;
  border-radius: 11px; background: var(--rc-noche); box-shadow: inset 0 -3px 0 var(--rc-marca); }
.rc-brand-icon svg { width: 22px; height: 22px; }
.rc-brand-name { color: var(--rc-ink); font-weight: 700; font-size: 1.04rem; letter-spacing: -.02em; line-height: 1.1; }
.rc-brand-meta { color: var(--rc-muted); font-size: .64rem; margin-top: .2rem;
  letter-spacing: .12em; text-transform: uppercase; font-family: var(--rc-monof); }

/* ---------- tarjeta de conexión (barra lateral) ---------- */
.rc-conexion { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); background: var(--rc-paper);
  padding: .7rem .8rem; margin: 0 0 .7rem; }
.rc-conexion-cab { display: flex; align-items: center; gap: .5rem; font-weight: 650; font-size: .86rem; color: var(--rc-ink); }
.rc-conexion-url { font-family: var(--rc-monof); font-size: .7rem; color: var(--rc-muted); margin-top: .25rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rc-conexion-pie { display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .55rem; }

/* ---------- banda de portada ---------- */
.rc-banda { position: relative; background: var(--rc-noche); border-radius: 14px; padding: 1.5rem 1.6rem 1.35rem;
  margin: 0 0 1.5rem; color: #fff; overflow: hidden; border-top: 3px solid var(--rc-cian); }
.rc-banda.ataque { border-top-color: var(--rc-red); }
.rc-banda.sano { border-top-color: var(--rc-ok); }
.rc-banda-eyebrow { font-family: var(--rc-monof); font-size: .66rem; font-weight: 600; letter-spacing: .16em;
  text-transform: uppercase; color: var(--rc-cian); margin: 0 0 .5rem; }
.rc-banda.ataque .rc-banda-eyebrow { color: #ff9a8c; }
.rc-banda-titulo { margin: 0 0 .4rem; font-size: clamp(1.5rem, 2.2vw, 2.05rem); line-height: 1.12;
  font-weight: 700; letter-spacing: -.03em; color: #fff; }
.rc-banda-sub { margin: 0; max-width: 72ch; font-size: .9rem; line-height: 1.55; color: rgba(255, 255, 255, .78); }
.rc-banda-cifras { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1px; margin-top: 1.4rem; background: rgba(255, 255, 255, .12); border-radius: 8px; overflow: hidden; }
.rc-banda-cifra { background: var(--rc-noche-2); padding: .85rem 1rem .8rem; }
.rc-banda-valor { font-size: clamp(1.4rem, 2.3vw, 1.95rem); font-weight: 650; line-height: 1.05;
  color: #fff; font-variant-numeric: tabular-nums; letter-spacing: -.03em; }
.rc-banda-etiqueta { margin-top: .4rem; font-size: .68rem; letter-spacing: .1em; text-transform: uppercase;
  color: rgba(255, 255, 255, .72); font-weight: 600; }
.rc-banda-nota { margin-top: .2rem; font-size: .74rem; color: rgba(255, 255, 255, .5); }

/* ---------- encabezado de página ---------- */
.rc-eyebrow { color: var(--rc-marca); font-family: var(--rc-monof); font-size: .66rem; font-weight: 600;
  letter-spacing: .14em; text-transform: uppercase; margin: 0 0 .4rem; }
.rc-titulo { margin: 0 0 .3rem; font-size: clamp(1.55rem, 2.3vw, 2.1rem); line-height: 1.12;
  font-weight: 700; letter-spacing: -.03em; color: var(--rc-ink); }
.rc-sub { max-width: 82ch; margin: 0 0 1.3rem; color: var(--rc-muted); font-size: .92rem; line-height: 1.55; }

/* ---------- secciones numeradas ---------- */
.rc-seccion { display: flex; align-items: baseline; gap: .65rem; margin: 2rem 0 .2rem;
  padding-bottom: .5rem; border-bottom: 1px solid var(--rc-line); }
.rc-seccion-num { font-family: var(--rc-monof); font-size: .7rem; font-weight: 600; color: var(--rc-marca);
  background: var(--rc-wash); border-radius: 6px; padding: .1rem .4rem; }
.rc-seccion-titulo { font-size: 1.05rem; font-weight: 650; color: var(--rc-ink); letter-spacing: -.01em; }
.rc-seccion-nota { margin-left: auto; font-size: .76rem; color: var(--rc-muted); text-align: right; }

/* ---------- tarjetas de indicador ---------- */
.rc-rejilla { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: .75rem; margin: .9rem 0 1.1rem; }
.rc-kpi { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); padding: .85rem .95rem;
  background: var(--rc-paper); box-shadow: var(--rc-sombra); border-left: 3px solid var(--rc-marca); }
.rc-kpi.alerta { border-left-color: var(--rc-red); }
.rc-kpi.neutra { border-left-color: var(--rc-line-2); }
.rc-kpi-etiqueta { font-size: .67rem; text-transform: uppercase; letter-spacing: .1em; color: var(--rc-muted); font-weight: 600; }
.rc-kpi-valor { margin-top: .38rem; font-size: clamp(1.3rem, 1.9vw, 1.7rem); font-weight: 650;
  color: var(--rc-ink); font-variant-numeric: tabular-nums; line-height: 1.1; letter-spacing: -.025em; }
.rc-kpi.alerta .rc-kpi-valor { color: var(--rc-red); }
.rc-kpi-nota { margin-top: .3rem; font-size: .74rem; color: var(--rc-muted); line-height: 1.4; }

/* ---------- indicadores de color ---------- */
.rc-indicadores { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .7rem; margin: .8rem 0 1rem; }
.rc-ind { --tono: var(--rc-marca); position: relative; overflow: hidden; display: flex; gap: .75rem; align-items: flex-start;
  border: 1px solid var(--rc-line); border-radius: var(--rc-radio); background: var(--rc-paper); padding: .8rem .9rem;
  box-shadow: var(--rc-sombra); animation: rc-subir .5s cubic-bezier(.2, .7, .2, 1) both; transition: transform .18s ease; }
.rc-ind:hover { transform: translateY(-2px); }
.rc-ind::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: var(--tono); opacity: .85; }
.rc-ind-chip { flex: none; display: grid; place-items: center; width: 36px; height: 36px; border-radius: 10px;
  font-family: var(--rc-monof); font-size: .7rem; font-weight: 600; color: var(--tono);
  background: color-mix(in srgb, var(--tono) 14%, transparent); }
.rc-ind-etiqueta { font-size: .66rem; text-transform: uppercase; letter-spacing: .1em; color: var(--rc-muted); font-weight: 600; }
.rc-ind-valor { font-size: 1.35rem; font-weight: 650; color: var(--rc-ink); font-variant-numeric: tabular-nums; letter-spacing: -.02em; line-height: 1.15; margin-top: .15rem; }
.rc-ind-nota { font-size: .72rem; color: var(--rc-muted); margin-top: .15rem; line-height: 1.35; }
.rc-ind.marca { --tono: var(--rc-marca); } .rc-ind.ok { --tono: var(--rc-ok); } .rc-ind.mal { --tono: var(--rc-red); }
.rc-ind.medio { --tono: var(--rc-amber); } .rc-ind.cielo { --tono: var(--rc-cielo); } .rc-ind.indigo { --tono: var(--rc-indigo); }
.rc-ind.rosa { --tono: var(--rc-rosa); }
.rc-indicadores > :nth-child(2) { animation-delay: .05s; } .rc-indicadores > :nth-child(3) { animation-delay: .1s; }
.rc-indicadores > :nth-child(4) { animation-delay: .15s; } .rc-indicadores > :nth-child(5) { animation-delay: .2s; }
.rc-indicadores > :nth-child(6) { animation-delay: .25s; } .rc-indicadores > :nth-child(7) { animation-delay: .3s; }
.rc-indicadores > :nth-child(8) { animation-delay: .35s; }

/* ---------- barras de métrica ---------- */
.rc-met { margin: .55rem 0 .2rem; }
.rc-met-fila { display: flex; justify-content: space-between; align-items: baseline;
  font-size: .8rem; color: var(--rc-ink-2); margin-bottom: .22rem; }
.rc-met-nombre { font-weight: 600; }
.rc-met-cifra { font-variant-numeric: tabular-nums; color: var(--rc-muted); font-size: .78rem; font-family: var(--rc-monof); }
.rc-met-pista { height: 6px; border-radius: 999px; background: var(--rc-pista); overflow: hidden; }
.rc-met-relleno { height: 100%; border-radius: 999px; background: var(--rc-ok); }
.rc-met-relleno.mal { background: var(--rc-red); }
.rc-met-relleno.medio { background: var(--rc-amber); }
.rc-met-relleno.marca { background: var(--rc-marca); }

/* ---------- tabla html ---------- */
.rc-tabla-envoltura { border: 1px solid var(--rc-line); border-radius: var(--rc-radio);
  background: var(--rc-paper); overflow-x: auto; margin: .7rem 0 1rem; box-shadow: var(--rc-sombra); }
table.rc-tabla { width: 100%; border-collapse: collapse; font-size: .82rem; }
table.rc-tabla th { text-align: left; font-size: .65rem; text-transform: uppercase; letter-spacing: .1em;
  color: var(--rc-muted); font-weight: 600; padding: .6rem .8rem; background: var(--rc-paper-2);
  border-bottom: 1px solid var(--rc-line); white-space: nowrap; }
table.rc-tabla td { padding: .55rem .8rem; border-bottom: 1px solid var(--rc-hover); color: var(--rc-ink-2); vertical-align: top; }
table.rc-tabla tr:last-child td { border-bottom: 0; }
table.rc-tabla tr:hover td { background: var(--rc-hover-suave); }
table.rc-tabla td.num, table.rc-tabla th.num { text-align: right; font-variant-numeric: tabular-nums; }
table.rc-tabla td.fuerte { color: var(--rc-ink); font-weight: 600; }

/* ---------- módulos ---------- */
.rc-modulos { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: .7rem; margin: .8rem 0 1.1rem; }
.rc-modulo { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); padding: .85rem .95rem;
  background: var(--rc-paper); box-shadow: var(--rc-sombra); }
.rc-modulo-cab { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.rc-modulo-id { font-family: var(--rc-monof); font-size: .72rem; font-weight: 600; color: var(--rc-marca); }
.rc-modulo-nombre { margin-top: .3rem; font-size: .92rem; font-weight: 650; color: var(--rc-ink); }
.rc-modulo-texto { margin-top: .3rem; font-size: .77rem; line-height: 1.45; color: var(--rc-muted); }
.rc-punto { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }
.rc-punto.ok { background: var(--rc-ok); box-shadow: 0 0 0 3px var(--rc-ok-wash); }
.rc-punto.mal { background: var(--rc-red); box-shadow: 0 0 0 3px var(--rc-red-wash); }
.rc-punto.medio { background: var(--rc-amber); box-shadow: 0 0 0 3px var(--rc-amber-wash); }

/* ---------- etiquetas y bloques ---------- */
.rc-pill { display: inline-flex; align-items: center; gap: .3rem; margin: 0 .28rem .32rem 0;
  padding: .24rem .6rem; border-radius: 999px; font-size: .7rem; font-weight: 600; border: 1px solid transparent; }
.rc-pill.ok { background: var(--rc-ok-wash); color: var(--rc-ok-txt); border-color: var(--rc-ok-borde); }
.rc-pill.mal { background: var(--rc-red-wash); color: var(--rc-red); border-color: var(--rc-red-borde); }
.rc-pill.medio { background: var(--rc-amber-wash); color: var(--rc-amber-txt); border-color: var(--rc-amber-borde); }
.rc-pill.neutra { background: var(--rc-hover); color: var(--rc-neutra-txt); border-color: var(--rc-line-2); }
.rc-pill.marca { background: var(--rc-wash); color: var(--rc-marca-osc); border-color: var(--rc-marca-borde); }
.rc-mono { font-family: var(--rc-monof); font-size: .8rem; }
.rc-aviso, .rc-nota, .rc-atencion { padding: .75rem .9rem; border-radius: 8px; font-size: .84rem; line-height: 1.55; margin: .5rem 0 .9rem; }
.rc-aviso { border: 1px solid var(--rc-red-borde); border-left: 3px solid var(--rc-red); background: var(--rc-red-wash); color: var(--rc-red-txt); }
.rc-atencion { border: 1px solid var(--rc-amber-borde); border-left: 3px solid var(--rc-amber); background: var(--rc-amber-wash); color: var(--rc-amber-txt); }
.rc-nota { border: 1px solid var(--rc-line); border-left: 3px solid var(--rc-marca); background: var(--rc-paper-2); color: var(--rc-neutra-txt); }
.rc-aviso strong, .rc-nota strong, .rc-atencion strong { color: inherit; }
.rc-fuente { font-size: .72rem; color: var(--rc-muted); margin: .2rem 0 .9rem; }

/* ---------- medidor de probabilidad ---------- */
.rc-prob { margin: .2rem 0 1.1rem; }
.rc-prob-cab { display: flex; justify-content: space-between; align-items: baseline;
  font-size: .74rem; color: var(--rc-muted); margin-bottom: .3rem; font-family: var(--rc-monof); }
.rc-prob-pista { position: relative; height: 10px; border-radius: 999px; background: var(--rc-pista); }
.rc-prob-relleno { height: 100%; border-radius: 999px; background: var(--rc-ok); }
.rc-prob-relleno.ataque { background: var(--rc-red); }
.rc-prob-marca { position: absolute; top: -4px; width: 2px; height: 18px; background: var(--rc-amber); }

/* ---------- controles nativos ---------- */
section[data-testid="stSidebar"] { background: var(--rc-paper-2); border-right: 1px solid var(--rc-line); }
section[data-testid="stSidebar"] > div { padding-top: 0; }
/* El encabezado nativo de la barra (solo el botón de plegar) ocupaba ~60 px
   encima del logo: se saca del flujo y se deja flotando a la derecha. */
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { position: absolute; top: .55rem; right: .4rem;
  height: auto; min-height: 0; padding: 0; margin: 0; z-index: 5; }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1rem; }
section[data-testid="stSidebar"] [data-testid="stLogoSpacer"] { display: none; }
header[data-testid="stHeader"] { background: transparent; height: 2.6rem; }
/* menú propio: secciones y enlaces debajo del logo */
.rc-nav-seccion { font-family: var(--rc-monof); font-size: .62rem; font-weight: 600; letter-spacing: .14em;
  text-transform: uppercase; color: var(--rc-muted); margin: .9rem 0 .15rem .35rem; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] { margin: 0; }
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] { border-radius: 8px; padding: .32rem .55rem; }
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover { background: var(--rc-hover); }
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"].active { background: var(--rc-wash); }
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] p,
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] span { color: var(--rc-marca-osc); font-weight: 600; }
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p { font-size: .9rem; color: var(--rc-ink-2); }

/* pantalla de acceso */
.rc-login-marca { display: flex; flex-direction: column; align-items: center; text-align: center; margin: 9vh 0 1.2rem; }
.rc-login-marca .rc-brand-icon { width: 56px; height: 56px; border-radius: 15px; }
.rc-login-marca .rc-brand-icon svg { width: 30px; height: 30px; }
.rc-login-titulo { margin: .9rem 0 .2rem; font-size: 1.5rem; font-weight: 700; letter-spacing: -.03em; color: var(--rc-ink); }
.rc-login-sub { margin: 0; font-size: .86rem; color: var(--rc-muted); }
.stButton button, .stDownloadButton button, .stFormSubmitButton button { border-radius: 8px; font-weight: 600; }
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] { background: var(--rc-marca); border-color: var(--rc-marca); color: #fff; }
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primary"]:hover { background: var(--rc-marca-osc); border-color: var(--rc-marca-osc); color: #fff; }
.stButton button[kind="secondary"]:hover, .stDownloadButton button:hover { border-color: var(--rc-marca); color: var(--rc-marca-osc); }
div[data-testid="stMetric"] { background: var(--rc-paper); border: 1px solid var(--rc-line); border-radius: var(--rc-radio); padding: .7rem .9rem; }
div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-size: 1.5rem; }
div[data-testid="stTabs"] button[role="tab"] p { font-weight: 600; }
div[data-testid="stDataFrame"] { border: 1px solid var(--rc-line); border-radius: var(--rc-radio); overflow: hidden; }
div[data-testid="stExpander"] details { background: var(--rc-paper); border: 1px solid var(--rc-line); border-radius: var(--rc-radio); }
div[data-testid="stForm"] { background: var(--rc-paper); border: 1px solid var(--rc-line); border-radius: var(--rc-radio); }
input, textarea, [data-baseweb="select"] > div { border-radius: 8px !important; }
#MainMenu, footer { visibility: hidden; }

/* ---------- movimiento ---------- */
@keyframes rc-subir { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes rc-aparecer { from { opacity: 0; } to { opacity: 1; } }
@keyframes rc-crecer { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes rc-girar { to { transform: rotate(360deg); } }
@keyframes rc-pulso-ok { 0% { box-shadow: 0 0 0 0 rgba(19, 134, 111, .5); } 70% { box-shadow: 0 0 0 8px rgba(19, 134, 111, 0); } 100% { box-shadow: 0 0 0 0 rgba(19, 134, 111, 0); } }
@keyframes rc-pulso-medio { 0% { box-shadow: 0 0 0 0 rgba(178, 107, 0, .5); } 70% { box-shadow: 0 0 0 8px rgba(178, 107, 0, 0); } 100% { box-shadow: 0 0 0 0 rgba(178, 107, 0, 0); } }
@keyframes rc-barrido { from { transform: translateX(-100%); } to { transform: translateX(100%); } }

.rc-banda { animation: rc-subir .6s cubic-bezier(.2, .7, .2, 1) both; }
.rc-banda > :not(.rc-radar) { position: relative; z-index: 1; }
.rc-banda-cifra { animation: rc-subir .55s cubic-bezier(.2, .7, .2, 1) both; }
.rc-banda-cifra:nth-child(2) { animation-delay: .07s; } .rc-banda-cifra:nth-child(3) { animation-delay: .14s; }
.rc-banda-cifra:nth-child(4) { animation-delay: .21s; } .rc-banda-cifra:nth-child(5) { animation-delay: .28s; }
.rc-radar { position: absolute; z-index: 0; right: -70px; top: -70px; width: 280px; height: 280px;
  border-radius: 50%; pointer-events: none; overflow: hidden;
  background: repeating-radial-gradient(circle, rgba(56, 198, 217, .16) 0 1px, transparent 1px 34px); }
.rc-radar::after { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, rgba(56, 198, 217, .32), rgba(56, 198, 217, 0) 70deg, transparent 360deg);
  animation: rc-girar 5s linear infinite; }
.rc-banda.ataque .rc-radar { background: repeating-radial-gradient(circle, rgba(255, 140, 120, .16) 0 1px, transparent 1px 34px); }
.rc-banda.ataque .rc-radar::after { background: conic-gradient(from 0deg, rgba(255, 140, 120, .35), rgba(255, 140, 120, 0) 70deg, transparent 360deg); }
.rc-vivo { display: inline-flex; align-items: center; gap: .4rem; margin-left: .6rem; padding: .1rem .5rem; border-radius: 999px;
  background: rgba(255, 255, 255, .08); color: rgba(255, 255, 255, .85); letter-spacing: .1em; }
.rc-vivo .rc-punto { width: 7px; height: 7px; }

.rc-kpi, .rc-modulo { animation: rc-subir .5s cubic-bezier(.2, .7, .2, 1) both; transition: transform .18s ease, box-shadow .18s ease; }
.rc-kpi:hover, .rc-modulo:hover { transform: translateY(-2px); box-shadow: 0 2px 4px rgba(13, 22, 38, .06), 0 14px 30px rgba(13, 22, 38, .08); }
.rc-rejilla > :nth-child(2), .rc-modulos > :nth-child(2) { animation-delay: .06s; }
.rc-rejilla > :nth-child(3), .rc-modulos > :nth-child(3) { animation-delay: .12s; }
.rc-rejilla > :nth-child(4), .rc-modulos > :nth-child(4) { animation-delay: .18s; }
.rc-rejilla > :nth-child(5), .rc-modulos > :nth-child(5) { animation-delay: .24s; }
.rc-rejilla > :nth-child(6), .rc-modulos > :nth-child(6) { animation-delay: .30s; }
.rc-met-relleno, .rc-prob-relleno { transform-origin: left center; animation: rc-crecer .9s cubic-bezier(.2, .7, .2, 1) both; }
.rc-tabla-envoltura, .rc-seccion { animation: rc-aparecer .5s ease both; }
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] { animation: rc-subir .7s cubic-bezier(.2, .7, .2, 1) both; }
.rc-punto.ok { animation: rc-pulso-ok 2.2s ease-out infinite; }
.rc-punto.medio { animation: rc-pulso-medio 2.2s ease-out infinite; }
.rc-panel-titulo { font-size: .67rem; text-transform: uppercase; letter-spacing: .1em; color: var(--rc-muted);
  font-weight: 600; text-align: center; margin-bottom: .1rem; }
.rc-vacio { position: relative; overflow: hidden; border: 1px dashed var(--rc-line-2); border-radius: var(--rc-radio);
  background: var(--rc-paper); padding: 1.4rem 1.2rem; text-align: center; margin: .8rem 0 1rem; }
.rc-vacio::before { content: ""; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(36, 80, 214, .07), transparent);
  animation: rc-barrido 2.6s ease-in-out infinite; }
.rc-vacio-titulo { position: relative; font-weight: 650; color: var(--rc-ink); font-size: .98rem; margin: 0 0 .25rem; }
.rc-vacio-texto { position: relative; color: var(--rc-muted); font-size: .85rem; margin: 0 auto; max-width: 62ch; line-height: 1.5; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}

@media (max-width: 760px) {
  .block-container { padding: 1rem .9rem 2rem; }
  .rc-banda { padding: 1.1rem 1.1rem 1rem; }
  .rc-radar { display: none; }
  .rc-rejilla { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; }
  .rc-kpi { padding: .7rem .75rem; }
  .rc-kpi-valor { font-size: 1.2rem; }
  .rc-seccion-nota { display: none; }
  table.rc-tabla { font-size: .76rem; }
}
</style>
"""

# Escudo con una red de tres nodos dentro y un barrido de radar: "centinela"
# que vigila una red. Un nodo va en rojo, el que el sistema marcó como hostil.
ESCUDO_SVG = (
    '<svg viewBox="0 0 32 32" fill="none" aria-hidden="true">'
    '<path d="M16 2.8 5.2 6.9v8.2c0 6.6 4.6 11.6 10.8 13.3 6.2-1.7 10.8-6.7 10.8-13.3V6.9L16 2.8Z" '
    'style="fill: var(--rc-marca, #2450d6)"/>'
    '<path d="M16 2.8 5.2 6.9v8.2c0 6.6 4.6 11.6 10.8 13.3 6.2-1.7 10.8-6.7 10.8-13.3V6.9L16 2.8Z" '
    'stroke="#38c6d9" stroke-width="1.3" stroke-linejoin="round"/>'
    '<path d="M16 15.5 L16 7.6 A7.9 7.9 0 0 1 23.1 12" fill="#38c6d9" fill-opacity=".28"/>'
    '<path d="M11 18.5 16 15.5l5.4 2.6M16 15.5l-1.2-5.6" stroke="#fff" stroke-width="1.4" '
    'stroke-linecap="round"/>'
    '<circle cx="16" cy="15.5" r="2.1" fill="#fff"/>'
    '<circle cx="11" cy="18.5" r="1.7" fill="#fff"/>'
    '<circle cx="14.8" cy="9.9" r="1.6" fill="#fff"/>'
    '<circle cx="21.4" cy="18.1" r="1.9" fill="#ff6b57" stroke="#fff" stroke-width="1"/>'
    "</svg>"
)


OSCURO = """
<style>
:root {
  --rc-ink: #e8edf6; --rc-ink-2: #cdd5e3; --rc-muted: #93a0b5;
  --rc-line: #243049; --rc-line-2: #33415e; --rc-paper: #121a2b; --rc-paper-2: #0f1626;
  --rc-canvas: #0a1020; --rc-hover: #1a2439; --rc-hover-suave: #151e31; --rc-pista: #222d44;
  --rc-campo: #18213a; --rc-noche: #0d1730; --rc-noche-2: #13213f;
  --rc-ok: #2fbf9b; --rc-ok-wash: rgba(47, 191, 155, .14); --rc-ok-txt: #7fe0c6; --rc-ok-borde: rgba(47, 191, 155, .35);
  --rc-red: #ff6b57; --rc-red-wash: rgba(255, 107, 87, .13); --rc-red-txt: #ffb3a8; --rc-red-borde: rgba(255, 107, 87, .35);
  --rc-amber: #f0a72f; --rc-amber-wash: rgba(240, 167, 47, .13); --rc-amber-txt: #f7cf8a; --rc-amber-borde: rgba(240, 167, 47, .35);
  --rc-neutra-txt: #b4bfd1; --rc-sombra: 0 1px 2px rgba(0, 0, 0, .3), 0 8px 24px rgba(0, 0, 0, .25);
}
.stApp, .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"] p { color: var(--rc-ink-2); }
.stApp [data-testid="stMarkdownContainer"] strong, .stApp summary, .stApp summary p { color: var(--rc-ink); }
section[data-testid="stSidebar"] { background: var(--rc-paper-2); }
.stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"], .stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"] > div, .stApp [data-testid="stNumberInputContainer"],
.stApp [data-testid="stFileUploaderDropzone"] { background: var(--rc-campo) !important; border-color: var(--rc-line-2) !important; }
.stApp input, .stApp textarea { color: var(--rc-ink) !important; -webkit-text-fill-color: var(--rc-ink); background: transparent !important; }
.stApp [data-baseweb="select"] *, .stApp [data-testid="stFileUploaderDropzone"] * { color: var(--rc-ink-2); }
.stApp [data-testid="stNumberInputContainer"] button { background: var(--rc-campo); color: var(--rc-ink-2); }
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] { background: var(--rc-paper) !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] [role="option"] { color: var(--rc-ink-2) !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] [aria-selected="true"] { background: var(--rc-hover) !important; }
[data-baseweb="tag"] { background: var(--rc-hover) !important; }
.stApp .stButton button[kind="secondary"], .stApp .stDownloadButton button, .stApp [data-testid="stBaseButton-secondary"],
.stApp [data-testid="stButtonGroup"] button { background: var(--rc-paper); color: var(--rc-ink); border-color: var(--rc-line-2); }
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"], .stApp [data-testid="stBaseButton-segmented_controlActive"] {
  background: var(--rc-wash); color: var(--rc-ink); border-color: var(--rc-marca); }
.stApp button[role="tab"] p { color: var(--rc-muted); } .stApp button[role="tab"][aria-selected="true"] p { color: var(--rc-ink); }
.stApp [data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--rc-line) !important; }
.stApp [data-testid="stExpander"] details, .stApp [data-testid="stForm"] { background: var(--rc-paper); border-color: var(--rc-line); }
.stApp [data-testid="stAlertContainer"] p, .stApp [data-testid="stAlertContainer"] { color: var(--rc-ink); }
.stApp [data-testid="stJson"], .stApp pre, .stApp [data-testid="stCode"] { background: var(--rc-paper-2) !important; }
.stApp [data-testid="stJson"] * { color: var(--rc-ink-2); }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color: var(--rc-muted); }
.stApp [data-testid="stSliderTickBarMin"], .stApp [data-testid="stSliderTickBarMax"], .stApp [data-testid="stSliderThumbValue"] { color: var(--rc-muted); }
.stApp [data-testid="stTooltipIcon"] svg { color: var(--rc-muted); }
.stApp [data-testid="stPageLink-NavLink"] p, .stApp [data-testid="stPageLink-NavLink"] span { color: var(--rc-ink-2); }
.stApp code { background: var(--rc-hover); }
.stApp hr { border-color: var(--rc-line) !important; }
</style>
"""

SIN_MOVIMIENTO = "<style>*, *::before, *::after { animation: none !important; transition: none !important; }</style>"

COMPACTA = """
<style>
.block-container { padding-top: .9rem; }
.rc-banda { padding: 1.05rem 1.2rem 1rem; margin-bottom: 1rem; }
.rc-banda-cifras { margin-top: .9rem; }
.rc-seccion { margin: 1.2rem 0 .1rem; }
.rc-rejilla, .rc-indicadores, .rc-modulos { gap: .5rem; margin: .5rem 0 .7rem; }
.rc-kpi, .rc-ind { padding: .6rem .7rem; }
table.rc-tabla td { padding: .38rem .7rem; } table.rc-tabla th { padding: .45rem .7rem; }
</style>
"""


PRESENTACION = """
<style>
.stApp { font-size: 1.08rem; }
.rc-titulo { font-size: clamp(2rem, 3vw, 2.7rem); }
.rc-banda-titulo { font-size: clamp(1.9rem, 3vw, 2.6rem); }
.rc-banda-valor { font-size: clamp(1.9rem, 3vw, 2.6rem); }
.rc-banda-sub, .rc-sub { font-size: 1.05rem; }
.rc-kpi-valor, .rc-ind-valor { font-size: 1.85rem; }
.rc-kpi-etiqueta, .rc-ind-etiqueta { font-size: .78rem; }
.rc-seccion-titulo { font-size: 1.35rem; }
table.rc-tabla { font-size: .95rem; }
.rc-fuente, .rc-seccion-nota, .rc-kpi-nota, .rc-ind-nota, .rc-banda-nota,
[data-testid="stCaptionContainer"] { display: none !important; }
</style>
"""

GUIA_CSS = """
<style>
.rc-guia { display: flex; gap: 1rem; align-items: flex-start; }
.rc-guia-num { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px;
  background: var(--rc-marca); color: #fff; font-family: var(--rc-monof); font-weight: 600; font-size: .95rem; }
.rc-guia-paso { font-family: var(--rc-monof); font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--rc-marca); font-weight: 600; }
.rc-guia-titulo { font-size: 1.05rem; font-weight: 650; color: var(--rc-ink); margin: .1rem 0 .25rem; }
.rc-guia-accion { font-size: .88rem; color: var(--rc-ink-2); margin: 0 0 .3rem; }
.rc-guia-guion { font-size: .84rem; color: var(--rc-muted); margin: 0; border-left: 3px solid var(--rc-line-2);
  padding-left: .6rem; font-style: italic; }
.rc-guia-barra { height: 4px; border-radius: 999px; background: var(--rc-pista); margin: .7rem 0 .2rem; overflow: hidden; }
.rc-guia-barra > div { height: 100%; background: var(--rc-marca); border-radius: 999px;
  transition: width .4s cubic-bezier(.2, .7, .2, 1); }
</style>
"""


def guia_cabecera(numero: int, total: int, titulo: str, accion: str, guion: str) -> None:
    """Encabezado del recorrido: número, qué hacer y qué decir."""
    st.markdown(GUIA_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="rc-guia"><div class="rc-guia-num">{numero}</div><div>'
        f'<div class="rc-guia-paso">Recorrido de la demo, paso {numero} de {total}</div>'
        f'<div class="rc-guia-titulo">{_esc(titulo)}</div>'
        f'<p class="rc-guia-accion">{_esc(accion)}</p>'
        f'<p class="rc-guia-guion">{_esc(guion)}</p></div></div>'
        f'<div class="rc-guia-barra"><div style="width:{100 * numero / total:.0f}%"></div></div>',
        unsafe_allow_html=True,
    )


def aplicar() -> None:
    """Inyecta los estilos del producto según las preferencias de la sesión."""
    from tablero.ui import preferencias

    principal, osc, lavado, claro = preferencias.acento()
    st.markdown(CSS, unsafe_allow_html=True)
    lavado_tema = f"color-mix(in srgb, {principal} 18%, transparent)" if preferencias.oscuro() else lavado
    st.markdown(
        f"<style>:root {{ --rc-marca: {principal}; --rc-marca-osc: {osc}; --rc-wash: {lavado_tema}; "
        f"--rc-marca-claro: {claro}; --rc-marca-borde: color-mix(in srgb, {principal} 30%, transparent); }}"
        "</style>",
        unsafe_allow_html=True,
    )
    if preferencias.oscuro():
        st.markdown(OSCURO, unsafe_allow_html=True)
    if not preferencias.obtener("animaciones"):
        st.markdown(SIN_MOVIMIENTO, unsafe_allow_html=True)
    if preferencias.obtener("densidad") == "Compacta":
        st.markdown(COMPACTA, unsafe_allow_html=True)
    if preferencias.obtener("presentacion"):
        st.markdown(PRESENTACION, unsafe_allow_html=True)


def _esc(valor: object) -> str:
    return _html.escape(str(valor), quote=False)


def marca(version: str) -> None:
    """Logotipo de la barra lateral."""
    st.markdown(
        '<div class="rc-brand"><div class="rc-brand-mark">'
        f'<div class="rc-brand-icon">{ESCUDO_SVG}</div>'
        '<div><div class="rc-brand-name">Red Centinela</div>'
        f'<div class="rc-brand-meta">Monitor de amenazas v{_esc(version)}</div></div>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def marca_login(version: str) -> None:
    """Logotipo grande centrado para la pantalla de acceso."""
    st.markdown(
        '<div class="rc-login-marca">'
        f'<div class="rc-brand-icon">{ESCUDO_SVG}</div>'
        '<p class="rc-login-titulo">Red Centinela</p>'
        f'<p class="rc-login-sub">Monitor de amenazas de red, versión {_esc(version)}</p></div>',
        unsafe_allow_html=True,
    )


def ocultar_barra_lateral() -> None:
    """Sin sesión no hay nada que navegar: se oculta la barra y su botón."""
    st.markdown(
        "<style>section[data-testid='stSidebar'], "
        "[data-testid='stSidebarCollapsedControl'], "
        "[data-testid='stExpandSidebarButton'] { display: none; }</style>",
        unsafe_allow_html=True,
    )


def sin_permiso(accion: str) -> None:
    """Explica por qué un control que escribe está deshabilitado para el rol lector."""
    bloque("Solo lectura.", f"Tu rol es <em>lector</em>: {accion} requiere el rol "
           "<em>admin</em>.", tono="nota")


def encabezado(titulo: str, subtitulo: str = "", eyebrow: str = "Centro de operaciones") -> None:
    st.markdown(f'<p class="rc-eyebrow">{_esc(eyebrow)}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="rc-titulo">{_esc(titulo)}</p>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<p class="rc-sub">{_esc(subtitulo)}</p>', unsafe_allow_html=True)


def banda(titulo: str, subtitulo: str, cifras: list[tuple], tono: str = "",
          eyebrow: str = "Centro de operaciones sobre NSL-KDD", vivo: bool = False) -> None:
    """Portada de la vista: título y hasta cinco cifras grandes.

    Cada cifra es (valor, etiqueta, nota). `tono` cambia el filete superior:
    '' (cian, informativo), 'ataque' (rojo) o 'sano' (verde azulado). `vivo`
    agrega la etiqueta "en línea" con el punto que late; solo se pasa cuando
    /health respondió en esta misma ejecución.
    """
    piezas = []
    for valor, etiqueta, nota in cifras:
        piezas.append(
            f'<div class="rc-banda-cifra"><div class="rc-banda-valor">{_esc(valor)}</div>'
            f'<div class="rc-banda-etiqueta">{_esc(etiqueta)}</div>'
            f'<div class="rc-banda-nota">{_esc(nota)}</div></div>'
        )
    chip = ('<span class="rc-vivo"><span class="rc-punto ok"></span>en línea</span>'
            if vivo else "")
    st.markdown(
        f'<div class="rc-banda {_esc(tono)}"><div class="rc-radar"></div>'
        f'<p class="rc-banda-eyebrow">{_esc(eyebrow)}{chip}</p>'
        f'<p class="rc-banda-titulo">{_esc(titulo)}</p>'
        f'<p class="rc-banda-sub">{_esc(subtitulo)}</p>'
        f'<div class="rc-banda-cifras">{"".join(piezas)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def seccion(numero: str, titulo: str, nota: str = "") -> None:
    """Encabezado de sección con número y regla inferior."""
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


def indicadores(items: list[tuple]) -> None:
    """Tarjetas de color: (chip, etiqueta, valor, nota, tono).

    El tono es semántico (ok, medio, mal) o de categoría (marca, cielo,
    indigo, rosa) para distinguir indicadores que no son buenos ni malos.
    """
    piezas = []
    for chip, etiqueta, valor, nota, tono in items:
        piezas.append(
            f'<div class="rc-ind {_esc(tono)}"><div class="rc-ind-chip">{_esc(chip)}</div><div>'
            f'<div class="rc-ind-etiqueta">{_esc(etiqueta)}</div>'
            f'<div class="rc-ind-valor">{_esc(valor)}</div>'
            f'<div class="rc-ind-nota">{_esc(nota)}</div></div></div>'
        )
    st.markdown(f'<div class="rc-indicadores">{"".join(piezas)}</div>', unsafe_allow_html=True)


def organico(texto: object) -> str:
    """Convierte separadores secos (punto y coma, barra vertical, punto medio)
    en frases: el tablero se lee como texto, no como una lista de campos.

    Se usa con las notas que vienen de la API (metrics.json), que no se editan
    desde el tablero.
    """
    limpio = str(texto or "").replace(" · ", ", ").replace(" | ", ", ")
    partes = [p.strip() for p in limpio.split(";") if p.strip()]
    if not partes:
        return ""
    frases = [partes[0][0].upper() + partes[0][1:]]
    frases += [p[0].upper() + p[1:] for p in partes[1:]]
    return ". ".join(f.rstrip(".") for f in frases) + "."


def pill(texto: str, tono: str = "neutra") -> str:
    """Devuelve HTML de una etiqueta de estado (ok, medio, mal, neutra, marca)."""
    return f'<span class="rc-pill {tono}">{_esc(texto)}</span>'


def barras(items: list[tuple], escala: float = 1.0) -> None:
    """Barras horizontales: (nombre, valor, texto, tono) con tono ok/medio/mal/marca."""
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
    """Tablero de módulos: (id, nombre, texto, estado) con estado ok/medio/mal."""
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


def panel_titulo(texto: str) -> None:
    """Rótulo centrado sobre una gráfica pequeña (medidores)."""
    st.markdown(f'<div class="rc-panel-titulo">{_esc(texto)}</div>', unsafe_allow_html=True)


def vacio(titulo: str, texto: str) -> None:
    """Estado vacío con un barrido suave: dice qué hacer para llenarlo."""
    st.markdown(
        f'<div class="rc-vacio"><p class="rc-vacio-titulo">{_esc(titulo)}</p>'
        f'<p class="rc-vacio-texto">{texto}</p></div>',
        unsafe_allow_html=True,
    )


def fuente(texto: str) -> None:
    """Línea de procedencia bajo una gráfica o tabla."""
    st.markdown(f'<p class="rc-fuente">{_esc(texto)}</p>', unsafe_allow_html=True)


def progress_probabilidad(probabilidad: float, umbral: float) -> None:
    """Medidor de p(ataque) con la marca del umbral de decisión.

    Se dibuja a mano en vez de con `st.progress` porque la marca del umbral es
    la información: sin ella, un 0.42 y un 0.98 se leen igual de "altos".
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
    """Muestra la salud real de la API como etiquetas."""
    if not estado:
        st.markdown(pill("API sin respuesta", "mal"), unsafe_allow_html=True)
        return
    disponibles = bool(estado.get("modelos_disponibles", True))
    integridad = "artefactos íntegros" if estado.get("integridad_artefactos") else "artefactos NO verificados"
    almacen = (estado.get("almacen") or {}).get("motor", "?")
    persistente = (estado.get("almacen") or {}).get("persistente")
    piezas = [
        pill(f"servicio {estado.get('status', '?')}",
             "ok" if estado.get("status") == "ok" else "medio"),
        pill(f"v{estado.get('version', '?')}", "neutra"),
        pill("modelos cargados" if disponibles else "modelos ausentes", "ok" if disponibles else "mal"),
        pill(integridad, "ok" if estado.get("integridad_artefactos") else "mal"),
        pill(f"umbral {estado.get('umbral_decision') or 'sin datos'}", "neutra"),
        pill(f"almacén {almacen}{'' if persistente else ' (no persiste)'}",
             "ok" if persistente else "neutra"),
    ]
    st.markdown(" ".join(piezas), unsafe_allow_html=True)


def tarjeta_conexion(url: str, estado: dict | None, latencia_ms: float | None = None) -> None:
    """Resumen de conexión para la barra lateral."""
    if estado is None:
        punto, titulo = "mal", "API sin respuesta"
        pie = [pill("revisa la URL o despierta el servicio", "mal")]
    elif estado.get("status") == "ok":
        punto, titulo = "ok", "En línea"
        pie = [pill(f"v{estado.get('version', '?')}", "neutra"),
               pill(f"umbral {estado.get('umbral_decision', '?')}", "neutra")]
    else:
        punto, titulo = "medio", "En línea, en modo degradado"
        pie = [pill("modelos ausentes" if not estado.get("modelos_disponibles")
                    else "artefactos no verificados", "medio")]
    if latencia_ms is not None:
        pie.append(pill("<1 ms" if latencia_ms < 1 else f"{latencia_ms:.0f} ms", "marca"))
    st.markdown(
        '<div class="rc-conexion"><div class="rc-conexion-cab">'
        f'<span class="rc-punto {punto}"></span>{_esc(titulo)}</div>'
        f'<div class="rc-conexion-url">{_esc(url)}</div>'
        f'<div class="rc-conexion-pie">{"".join(pie)}</div></div>',
        unsafe_allow_html=True,
    )


def aviso_degradado(estado: dict | None, contexto: str = "") -> bool:
    """Si la API responde pero sin modelos, lo explica y devuelve True.

    En ese modo /predict responde 503: cualquier botón de predicción se
    deshabilita en vez de fallar al pulsarlo.
    """
    if not estado or estado.get("modelos_disponibles", True):
        return False
    bloque(
        "API en modo degradado: los modelos no están cargados.",
        "El servicio responde, el historial y las métricas publicadas se leen, pero "
        "<span class='rc-mono'>/predict</span> devuelve 503 hasta que existan los "
        "<span class='rc-mono'>.joblib</span>. Genéralos con "
        "<span class='rc-mono'>python -m cli train</span> o descárgalos con "
        "<span class='rc-mono'>python scripts/descargar_artefactos.py</span>. "
        + contexto,
        tono="atencion",
    )
    return True


def bloque(titulo: str, texto: str, tono: str = "nota") -> None:
    """Panel compacto: tono 'nota' (azul), 'atencion' (ámbar) o 'aviso' (rojo)."""
    clase = {"aviso": "rc-aviso", "atencion": "rc-atencion"}.get(tono, "rc-nota")
    st.markdown(f'<div class="{clase}"><strong>{titulo}</strong> {texto}</div>',
                unsafe_allow_html=True)
