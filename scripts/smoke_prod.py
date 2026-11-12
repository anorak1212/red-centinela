"""Script de humo contra una API real (local o desplegada).

Comprueba, en este orden y sin inventar nada:

    1. GET  /health                      debe responder 200 y con artefactos íntegros
    2. GET  /metrics                     cifras del modelo
    3. POST /predict                     una conexión normal
    4. POST /predict/batch               la muestra indicada en --muestra
    5. GET  /history                     el registro recién creado sigue ahí
    6. latencia p95 de /predict          N peticiones medidas, no estimadas
    7. GET  del tablero                  debe responder 200 (si se pasa --tablero)
    8. alerta de Telegram                si se pasa --telegram y hay bot configurado

Uso:
    python -m scripts.smoke_prod --api http://127.0.0.1:8000
    python -m scripts.smoke_prod --api https://red-centinela-api.onrender.com \
        --tablero https://red-centinela.streamlit.app \
        --muestra datasets/sample_trafico.csv --esperado-ataques 30

Con una muestra sin columna `family` no se pueden medir familias: se compara el
número de ataques predichos contra --esperado-ataques y se dice cuál era.

Todo lo que no se pueda comprobar se reporta como SALTADO o FALLO; nunca se
declara éxito sin evidencia.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
MUESTRA = RAIZ / "datasets" / "sample_etiquetado.csv"
TIMEOUT = 60

_FILA_NORMAL = {
    "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "SF",
    "src_bytes": 232, "dst_bytes": 8153, "land": 0, "wrong_fragment": 0,
    "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 1,
    "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
    "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
    "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
    "count": 5, "srv_count": 5, "serror_rate": 0.0, "srv_serror_rate": 0.0,
    "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
    "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 30,
    "dst_host_srv_count": 255, "dst_host_same_srv_rate": 1.0,
    "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 0.03,
    "dst_host_srv_diff_host_rate": 0.04, "dst_host_serror_rate": 0.0,
    "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 0.0,
    "dst_host_srv_rerror_rate": 0.0,
}


class Resultado:
    """Una fila de la tabla final."""

    def __init__(self) -> None:
        self.filas: list[tuple[str, str, str]] = []

    def add(self, prueba: str, estado: str, detalle: str) -> None:
        self.filas.append((prueba, estado, detalle))

    @property
    def fallos(self) -> int:
        return sum(1 for _, e, _ in self.filas if e == "FALLO")

    def imprimir(self) -> None:
        ancho = max(len(p) for p, _, _ in self.filas)
        print()
        print(f"{'PRUEBA'.ljust(ancho)}  ESTADO    DETALLE")
        print("-" * (ancho + 60))
        for prueba, estado, detalle in self.filas:
            print(f"{prueba.ljust(ancho)}  {estado.ljust(9)} {detalle}")
        print()


def _esperar_despierto(api: str, limite: int, res: Resultado) -> bool:
    """Los servicios gratuitos se duermen: se les da tiempo a arrancar."""
    t0 = time.time()
    intento = 0
    while time.time() - t0 < limite:
        intento += 1
        try:
            r = requests.get(f"{api}/health", timeout=20)
            if r.status_code == 200:
                espera = time.time() - t0
                res.add(
                    "arranque en frío",
                    "OK",
                    f"{espera:.1f} s tras {intento} intento(s)"
                    if espera > 3 else f"ya estaba despierto ({espera:.1f} s)",
                )
                return True
        except requests.RequestException:
            pass
        time.sleep(5)
    res.add("arranque en frío", "FALLO", f"no respondió en {limite} s")
    return False


def _health(api: str, res: Resultado) -> dict:
    r = requests.get(f"{api}/health", timeout=TIMEOUT)
    body = r.json() if r.status_code == 200 else {}
    estado = "OK" if r.status_code == 200 and body.get("status") == "ok" else "FALLO"
    res.add(
        "GET /health",
        estado,
        f"{r.status_code}, integridad={body.get('integridad_artefactos')}, "
        f"umbral={body.get('umbral_decision')}, "
        f"almacén={(body.get('almacen') or {}).get('motor')}",
    )
    return body


def _metrics(api: str, res: Resultado) -> None:
    r = requests.get(f"{api}/metrics", timeout=TIMEOUT)
    if r.status_code != 200:
        res.add("GET /metrics", "FALLO", f"{r.status_code}")
        return
    m = r.json()
    res.add(
        "GET /metrics",
        "OK",
        f"macro-F1 binario {m['binario_kddtest']['macro_f1']}, "
        f"5 clases {m['multiclase_kddtest']['macro_f1']}, "
        f"generado {m.get('generado', '?')}",
    )


def _predict_una(api: str, res: Resultado) -> int | None:
    r = requests.post(f"{api}/predict", json={"features": _FILA_NORMAL}, timeout=TIMEOUT)
    if r.status_code != 200:
        res.add("POST /predict normal", "FALLO", f"{r.status_code} {r.text[:120]}")
        return None
    body = r.json()
    esperado = body["etiqueta"] == "normal"
    res.add(
        "POST /predict normal",
        "OK" if esperado else "FALLO",
        f"{r.status_code}, etiqueta={body['etiqueta']}, "
        f"p(ataque)={body['probabilidad_ataque']}, id={body['id']}",
    )
    return int(body["id"])


def _predict_lote(api: str, res: Resultado, ruta: Path,
                  esperado: int | None) -> list[int]:
    if not ruta.exists():
        res.add("POST /predict/batch", "SALTADO",
                f"falta {ruta}; indícalo con --muestra")
        return []

    df = pd.read_csv(ruta)
    etiquetas = [c for c in ("label", "family") if c in df.columns]
    items = [
        {"features": {k: (str(v) if k in ("protocol_type", "service", "flag") else v)
                      for k, v in fila.items()}}
        for fila in df.drop(columns=etiquetas).to_dict("records")
    ]
    r = requests.post(f"{api}/predict/batch", json={"items": items}, timeout=TIMEOUT)
    if r.status_code != 200:
        res.add("POST /predict/batch", "FALLO", f"{r.status_code} {r.text[:120]}")
        return []

    body = r.json()
    pred = pd.DataFrame(body["resultados"])
    ataques = int(pred["es_ataque"].sum())
    reparto = ", ".join(
        f"{c} {int(n)}" for c, n in pred["clase"].value_counts().items()
    )

    if "family" in df.columns:
        pred["real"] = df["family"].to_numpy()
        pred["es_ataque_real"] = pred["real"] != "normal"
        reales = pred[pred["es_ataque_real"]]
        normales = pred[~pred["es_ataque_real"]]
        detectados = int(reales["es_ataque"].sum())
        falsos = int(normales["es_ataque"].sum())
        detalle_familias = ", ".join(
            f"{f} {int(g['es_ataque'].sum())}/{len(g)}"
            for f, g in reales.groupby("real")
        )
        estado = "OK" if detectados == len(reales) and falsos == 0 else "PARCIAL"
        res.add(
            "POST /predict/batch",
            estado,
            f"{body['total']} filas, ataques {detectados}/{len(reales)} "
            f"({detalle_familias}), falsos positivos {falsos}/{len(normales)}",
        )
    else:
        # Muestra sin etiquetas: lo único honesto es comparar contra el número
        # esperado que declara quien llama, y decir cuál era.
        if esperado is None:
            estado = "INFORMATIVO"
            detalle = f"{body['total']} filas, {ataques} ataques predichos ({reparto})"
        else:
            estado = "OK" if ataques == esperado else "FALLO"
            detalle = (f"{body['total']} filas, {ataques} ataques predichos, "
                       f"esperados {esperado} ({reparto})")
        res.add("POST /predict/batch", estado, detalle)
    return [int(body["resultados"][0]["id"]), int(body["resultados"][-1]["id"])]


def _history(api: str, ids: list[int], res: Resultado) -> None:
    r = requests.get(f"{api}/history?limit=200", timeout=TIMEOUT)
    if r.status_code != 200:
        res.add("GET /history", "FALLO", f"{r.status_code}")
        return
    body = r.json()
    presentes = {f["id"] for f in body["predicciones"]}
    faltan = [i for i in ids if i not in presentes]
    res.add(
        "GET /history",
        "OK" if not faltan else "FALLO",
        f"{body['total']} registros, almacén "
        f"{(body.get('almacen') or {}).get('motor')}, "
        f"ids verificados {len(ids) - len(faltan)}/{len(ids)}",
    )


def _latencia(api: str, res: Resultado, n: int) -> None:
    tiempos: list[float] = []
    fallos = 0
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            r = requests.post(
                f"{api}/predict", json={"features": _FILA_NORMAL}, timeout=TIMEOUT
            )
            if r.status_code != 200:
                fallos += 1
                continue
        except requests.RequestException:
            fallos += 1
            continue
        tiempos.append((time.perf_counter() - t0) * 1000)

    if not tiempos:
        res.add("latencia p95 /predict", "FALLO", "ninguna petición completada")
        return
    tiempos.sort()
    p95 = tiempos[max(0, round(0.95 * len(tiempos)) - 1)]
    mediana = statistics.median(tiempos)
    estado = "OK" if p95 <= 200 else "PARCIAL"
    res.add(
        "latencia p95 /predict",
        estado,
        f"p95 {p95:.0f} ms, mediana {mediana:.0f} ms, n={len(tiempos)}"
        f"{f', fallos {fallos}' if fallos else ''} (objetivo <= 200 ms)",
    )


def _tablero(url: str, res: Resultado) -> None:
    try:
        r = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        res.add("tablero HTTP 200", "FALLO", type(exc).__name__)
        return
    res.add(
        "tablero HTTP 200",
        "OK" if r.status_code == 200 else "FALLO",
        f"{r.status_code}, {len(r.content)} bytes",
    )


def _telegram(api: str, res: Resultado) -> None:
    r = requests.get(f"{api}/alertas/estado", timeout=TIMEOUT)
    if r.status_code != 200:
        res.add("alerta Telegram", "FALLO", f"/alertas/estado {r.status_code}")
        return
    estado = r.json()
    if not estado.get("configurado"):
        res.add("alerta Telegram", "SALTADO",
                "sin REDCENTINELA_TELEGRAM_TOKEN/CHAT_ID en el servicio")
        return
    t0 = time.time()
    r = requests.post(f"{api}/predict", json={"features": _FILA_NORMAL}, timeout=TIMEOUT)
    res.add(
        "alerta Telegram",
        "INFORMATIVO",
        f"envío disparado en {time.time() - t0:.1f} s; la recepción en el chat "
        "debe confirmarse a ojo (fallidos="
        f"{estado.get('fallidos')}, enviados={estado.get('enviados')})",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Humo contra la API de Red Centinela.")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--tablero", default=None, help="URL del tablero Streamlit")
    p.add_argument("--telegram", action="store_true", help="probar el envío de alertas")
    p.add_argument("--latencia", type=int, default=30, help="peticiones medidas")
    p.add_argument("--espera", type=int, default=120, help="segundos de arranque en frío")
    p.add_argument("--muestra", default=str(MUESTRA),
                   help="CSV para /predict/batch (con etiquetas o sin ellas)")
    p.add_argument("--esperado-ataques", type=int, default=None,
                   help="ataques que debe predecir la muestra sin etiquetas")
    args = p.parse_args(argv)

    api = args.api.rstrip("/")
    res = Resultado()
    print(f"API: {api}")

    if not _esperar_despierto(api, args.espera, res):
        res.imprimir()
        return 1

    _health(api, res)
    _metrics(api, res)
    ident = _predict_una(api, res)
    ids = _predict_lote(api, res, Path(args.muestra), args.esperado_ataques)
    if ident is not None:
        ids = [ident, *ids]
    if ids:
        _history(api, ids, res)
    _latencia(api, res, args.latencia)
    if args.tablero:
        _tablero(args.tablero, res)
    if args.telegram:
        _telegram(api, res)

    res.imprimir()
    print(json.dumps({"fallos": res.fallos}, ensure_ascii=False))
    return 0 if res.fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
