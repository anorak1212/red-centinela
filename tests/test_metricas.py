"""Pruebas de las funciones puras de evaluación y calibración.

No se ejecuta `train.main()` ni `evaluate.main()`: entrenan modelos reales sobre
125,973 filas y reescriben los artefactos. Lo que se prueba aquí es la lógica de
cálculo, que es donde vive el riesgo de un error silencioso.
"""

from __future__ import annotations

import numpy as np
from motor.evaluate import _bloque_binario, _bloque_multiclase, _tabla
from motor.train import _calibrar_umbral


def test_bloque_binario_aciertos_perfectos():
    y = np.array([0, 0, 1, 1])
    proba = np.array([0.1, 0.2, 0.8, 0.9])
    r = _bloque_binario(y, (proba >= 0.5).astype(int), proba)
    assert r["accuracy"] == 1.0
    assert r["macro_f1"] == 1.0
    assert r["recall_ataque"] == 1.0
    assert r["auc_roc"] == 1.0
    assert r["filas"] == 4
    assert r["ataques_reales"] == 2
    assert r["matriz_confusion"] == [[2, 0], [0, 2]]


def test_bloque_binario_todo_normal():
    """El caso degenerado que rompía el cálculo: sin falsos positivos."""
    y = np.array([0, 0, 0, 1])
    proba = np.array([0.1, 0.1, 0.1, 0.2])
    r = _bloque_binario(y, np.zeros(4, dtype=int), proba)
    assert r["recall_ataque"] == 0.0
    assert r["precision_ataque"] == 0.0
    assert r["macro_f1"] < 0.6


def test_bloque_binario_matriz_cuadra():
    y = np.array([0, 0, 1, 1, 1])
    yhat = np.array([0, 1, 1, 0, 1])
    r = _bloque_binario(y, yhat, np.linspace(0.1, 0.9, 5))
    m = r["matriz_confusion"]
    assert sum(m[0]) + sum(m[1]) == len(y)


def test_bloque_multiclase_estructura():
    y = np.array([0, 0, 1, 2, 3, 4])
    yhat = np.array([0, 0, 1, 2, 1, 1])
    r = _bloque_multiclase(y, yhat)
    assert set(r["por_clase"]) == {"normal", "dos", "probe", "r2l", "u2r"}
    assert r["filas"] == 6
    assert len(r["matriz_confusion"]) == 5
    assert r["por_clase"]["normal"]["recall"] == 1.0
    assert r["por_clase"]["u2r"]["recall"] == 0.0


def test_bloque_multiclase_clase_ausente_no_explota():
    y = np.array([0, 0, 1, 1])
    yhat = np.array([0, 1, 1, 1])
    r = _bloque_multiclase(y, yhat)
    assert r["por_clase"]["u2r"]["soporte"] == 0
    assert 0.0 <= r["macro_f1"] <= 1.0


def test_calibrar_umbral_elige_el_extremo_util():
    """Con señales separables, el umbral debe caer entre las dos nubes."""
    y = np.array([0] * 50 + [1] * 50)
    proba = np.concatenate([np.full(50, 0.1), np.full(50, 0.9)])
    cal = _calibrar_umbral(proba, y)
    assert 0.1 < cal["umbral_decision"] <= 0.9
    assert cal["macro_f1_binario_holdout"] == 1.0


def test_calibrar_umbral_caso_solapado():
    rng = np.random.default_rng(0)
    y = np.array([0] * 200 + [1] * 200)
    proba = np.concatenate([rng.normal(0.4, 0.2, 200), rng.normal(0.6, 0.2, 200)])
    proba = np.clip(proba, 0, 1)
    cal = _calibrar_umbral(proba, y)
    assert 0.2 <= cal["umbral_decision"] <= 0.7
    assert 0.5 <= cal["macro_f1_binario_holdout"] <= 1.0


def test_tabla_markdown():
    texto = _tabla([("A", 1), ("B", 2.5)])
    assert texto.startswith("| Métrica | Valor |")
    assert "| A | 1 |" in texto
    assert "| B | 2.5 |" in texto
