"""Pruebas del CLI (M6, actividad A30)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli.__main__ import (
    SALIDA_ERROR_ENTRADA,
    SALIDA_OK,
    SALIDA_SIN_MODELOS,
    construir_parser,
    main,
)
from motor.data import MODEL_DIR

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "datasets" / "sample_trafico.csv"
_HAY_MODELOS = (MODEL_DIR / "manifiesto.json").exists()


def test_parser_exige_comando():
    with pytest.raises(SystemExit):
        construir_parser().parse_args([])


def test_parser_reconoce_comandos():
    p = construir_parser()
    for comando in ("train", "evaluate", "estado", "predict", "serve", "alerta-prueba"):
        assert p.parse_args([comando] + (["x.csv"] if comando == "predict" else []))


def test_estado_sin_modelos_avisa(tmp_path, monkeypatch, capsys):
    import motor.ensemble as ensamble

    monkeypatch.setattr("motor.data.MODEL_DIR", tmp_path)
    monkeypatch.setattr(ensamble, "MODEL_DIR", tmp_path)
    assert main(["estado"]) == SALIDA_SIN_MODELOS
    assert "Sin modelos" in capsys.readouterr().out


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_estado_con_modelos(capsys):
    assert main(["estado"]) == SALIDA_OK
    salida = capsys.readouterr().out
    assert "Umbral de decision" in salida
    assert "Artefactos integros: si" in salida


def test_predict_archivo_inexistente(capsys):
    assert main(["predict", "no_existe_jamas.csv"]) == SALIDA_ERROR_ENTRADA
    assert "No existe" in capsys.readouterr().err


@pytest.mark.skipif(not _HAY_MODELOS, reason="sin artefactos el CLI avisa antes de leer el CSV")
def test_predict_csv_sin_columnas(tmp_path, capsys):
    malo = tmp_path / "malo.csv"
    malo.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    assert main(["predict", str(malo)]) == SALIDA_ERROR_ENTRADA
    assert "Faltan" in capsys.readouterr().err


@pytest.mark.skipif(not (_HAY_MODELOS and SAMPLE.exists()),
                    reason="modelos o muestra no disponibles")
def test_predict_archivo_real(tmp_path, capsys):
    salida = tmp_path / "resultado.csv"
    codigo = main(["predict", str(SAMPLE), "--salida", str(salida)])
    assert codigo == SALIDA_OK
    assert salida.exists()
    texto = capsys.readouterr().out
    assert "Ataques detectados" in texto

    import pandas as pd

    df = pd.read_csv(salida)
    assert len(df) >= 30
    assert {"es_ataque", "clase", "probabilidad_ataque"} <= set(df.columns)
    assert df["clase"].isin(["normal", "dos", "probe", "r2l", "u2r"]).all()
