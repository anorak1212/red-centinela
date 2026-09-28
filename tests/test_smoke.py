"""Prueba de humo: verifica la instalación del entorno base."""


def test_imports_de_la_pila():
    import joblib  # noqa: F401
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import sklearn  # noqa: F401

    assert hasattr(sklearn, "__version__")


def test_operacion_simple_de_numpy():
    import numpy as np

    vector = np.array([1.0, 2.0, 3.0])
    assert float(vector.mean()) == 2.0