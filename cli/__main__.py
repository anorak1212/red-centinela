"""CLI de Red Centinela (M6, actividad A30).

    python -m cli train                  entrena y guarda artefactos
    python -m cli evaluate               evalúa sobre KDDTest+ y escribe métricas
    python -m cli predict archivo.csv    clasifica un CSV y escribe resultados
    python -m cli serve                  arranca la API en local
    python -m cli estado                 muestra versión, modelos y métricas
    python -m cli alerta-prueba          envía un mensaje de prueba por Telegram

Todo reutiliza motor/, api/ y alertas/: el CLI no tiene lógica de detección
propia. Los códigos de retorno distinguen el tipo de fallo para poder encadenarlo
en un script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SALIDA_OK = 0
SALIDA_ERROR_ENTRADA = 2
SALIDA_SIN_MODELOS = 3


def _cmd_train(args) -> int:
    from motor.train import main

    main()
    return SALIDA_OK


def _cmd_evaluate(args) -> int:
    from motor.evaluate import main

    main()
    return SALIDA_OK


def _cmd_estado(args) -> int:
    from motor.data import MODEL_DIR
    from motor.ensemble import verificar_manifiesto

    md_path = MODEL_DIR / "metadata.json"
    if not md_path.exists():
        print("Sin modelos. Ejecuta: python -m cli train")
        return SALIDA_SIN_MODELOS
    md = json.loads(md_path.read_text(encoding="utf-8"))
    integridad = verificar_manifiesto(MODEL_DIR)
    print(f"Red Centinela  version de motor {md.get('version')}")
    print(f"Modelo de produccion: {md.get('modelo_produccion')} "
          f"({', '.join(md.get('modelos', []))})")
    print(f"Umbral de decision: {md.get('umbral_decision')}")
    print(f"Artefactos integros: {'si' if integridad['ok'] else 'NO'}")
    if not integridad["ok"]:
        for nombre, estado in integridad["detalle"].items():
            if estado != "ok":
                print(f"  {nombre}: {estado}")
    ruta = MODEL_DIR / "metrics.json"
    if ruta.exists():
        m = json.loads(ruta.read_text(encoding="utf-8"))
        b = m.get("binario_kddtest", {})
        mc = m.get("multiclase_kddtest", {})
        print(f"KDDTest+ binario: macro-F1 {b.get('macro_f1')}  "
              f"exactitud {b.get('accuracy')}  AUC {b.get('auc_roc')}")
        print(f"KDDTest+ 5 clases: macro-F1 {mc.get('macro_f1')}  "
              f"weighted-F1 {mc.get('weighted_f1')}")
    return SALIDA_OK


def _cmd_predict(args) -> int:
    import pandas as pd
    from motor.data import FEATURE_NAMES, MODEL_DIR
    from motor.ensemble import (
        cargar_modelos,
        etiqueta_clase,
        predecir,
        predecir_multiclase,
    )

    entrada = Path(args.archivo)
    if not entrada.exists():
        print(f"No existe el archivo: {entrada}", file=sys.stderr)
        return SALIDA_ERROR_ENTRADA
    if not (MODEL_DIR / "metadata.json").exists():
        print("Sin modelos entrenados. Ejecuta: python -m cli train", file=sys.stderr)
        return SALIDA_SIN_MODELOS

    try:
        df = pd.read_csv(entrada)
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo leer el CSV: {type(exc).__name__}", file=sys.stderr)
        return SALIDA_ERROR_ENTRADA

    faltan = [c for c in FEATURE_NAMES if c not in df.columns]
    if faltan:
        print(f"Faltan {len(faltan)} columnas: {', '.join(faltan[:10])}", file=sys.stderr)
        return SALIDA_ERROR_ENTRADA
    if df.empty:
        print("El archivo no tiene filas.", file=sys.stderr)
        return SALIDA_ERROR_ENTRADA

    modelos = cargar_modelos(MODEL_DIR, verificar=True)
    md = modelos["metadata"]
    umbral = float(md["umbral_decision"])

    filas = df[FEATURE_NAMES].copy()
    for col in ("protocol_type", "service", "flag"):
        filas[col] = filas[col].astype(str).str.lower()

    X = modelos["preprocessor"].transform(filas)
    yhat, proba = predecir(modelos, X, umbral)
    idx, proba_multi = predecir_multiclase(modelos, X)

    df["es_ataque"] = yhat.astype(bool)
    df["clase"] = [etiqueta_clase(i) for i in idx]
    df["probabilidad_ataque"] = [round(float(p), 4) for p in proba]
    df["probabilidad_clase"] = [
        round(float(proba_multi[n][i]), 4) for n, i in enumerate(idx)
    ]
    if "label" in df.columns:
        df["etiqueta_real"] = df["label"]

    salida = Path(args.salida) if args.salida else entrada.with_name(
        f"{entrada.stem}_resultado.csv"
    )
    df.to_csv(salida, index=False)

    total = len(df)
    ataques = int(df["es_ataque"].sum())
    print(f"Archivo: {entrada.name}")
    print(f"Registros: {total}")
    print(f"Ataques detectados: {ataques} ({ataques / total:.1%})")
    print(f"Normales: {total - ataques}")
    print("Distribucion por clase:")
    for clase, n in df["clase"].value_counts().items():
        print(f"  {clase}: {n}")
    print(f"Resultado escrito en: {salida}")

    if "label" in df.columns:
        real = (df["label"].astype(str) != "normal").to_numpy()
        aciertos = int((df["es_ataque"].to_numpy() == real).sum())
        print(f"Contra la columna label del archivo: {aciertos}/{total} "
              f"({aciertos / total:.1%})")
    return SALIDA_OK


def _cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("api.main:app", host=args.host, port=args.puerto, reload=args.recarga)
    return SALIDA_OK


def _cmd_alerta_prueba(args) -> int:
    from alertas import telegram

    print(json.dumps(telegram.estado(), ensure_ascii=False, indent=2))
    resultado = telegram.enviar_prueba()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return SALIDA_OK if resultado.get("ok") else 1


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="redcentinela",
        description="Detección de tráfico de red anómalo con NSL-KDD.",
    )
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("train", help="entrena los modelos y guarda los artefactos")
    sub.add_parser("evaluate", help="evalúa sobre KDDTest+ y escribe metrics.json")
    sub.add_parser("estado", help="muestra versión, integridad y métricas")

    pp = sub.add_parser("predict", help="clasifica un CSV con las 41 columnas")
    pp.add_argument("archivo", help="ruta del CSV de entrada")
    pp.add_argument("--salida", help="ruta del CSV de resultados")

    ps = sub.add_parser("serve", help="arranca la API en local")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--puerto", type=int, default=8000)
    ps.add_argument("--recarga", action="store_true", help="recarga automática")

    sub.add_parser("alerta-prueba", help="envía un mensaje de prueba por Telegram")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    despacho = {
        "train": _cmd_train,
        "evaluate": _cmd_evaluate,
        "estado": _cmd_estado,
        "predict": _cmd_predict,
        "serve": _cmd_serve,
        "alerta-prueba": _cmd_alerta_prueba,
    }
    return despacho[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
