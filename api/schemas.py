"""Esquemas Pydantic de la API (validación estricta, SEG-007).

Cada uno de los 41 campos de NSL-KDD se declara con tipo y rango. `extra="forbid"`
hace que un campo desconocido devuelva 422 en lugar de ignorarse en silencio, que
es lo que permite declarar la validación como control real y no decorativo.

Los rangos no son inventados: `src_bytes` y `dst_bytes` son conteos (no negativos),
las tasas de error y de servicio son proporciones (0 a 1) y las banderas son
binarias salvo `su_attempted`, que en el dataset toma 0, 1 y 2.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FilaTrafico(BaseModel):
    """Una conexión NSL-KDD completa."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    duration: float = Field(..., ge=0, description="Duración en segundos")
    protocol_type: str = Field(..., min_length=1, max_length=10)
    service: str = Field(..., min_length=1, max_length=40)
    flag: str = Field(..., min_length=1, max_length=10)
    src_bytes: float = Field(..., ge=0)
    dst_bytes: float = Field(..., ge=0)
    land: int = Field(..., ge=0, le=1)
    wrong_fragment: float = Field(..., ge=0)
    urgent: float = Field(..., ge=0)
    hot: float = Field(..., ge=0)
    num_failed_logins: float = Field(..., ge=0)
    logged_in: int = Field(..., ge=0, le=1)
    num_compromised: float = Field(..., ge=0)
    root_shell: int = Field(..., ge=0, le=1)
    su_attempted: int = Field(..., ge=0, le=2)
    num_root: float = Field(..., ge=0)
    num_file_creations: float = Field(..., ge=0)
    num_shells: float = Field(..., ge=0)
    num_access_files: float = Field(..., ge=0)
    num_outbound_cmds: float = Field(..., ge=0)
    is_host_login: int = Field(..., ge=0, le=1)
    is_guest_login: int = Field(..., ge=0, le=1)
    count: float = Field(..., ge=0)
    srv_count: float = Field(..., ge=0)
    serror_rate: float = Field(..., ge=0, le=1)
    srv_serror_rate: float = Field(..., ge=0, le=1)
    rerror_rate: float = Field(..., ge=0, le=1)
    srv_rerror_rate: float = Field(..., ge=0, le=1)
    same_srv_rate: float = Field(..., ge=0, le=1)
    diff_srv_rate: float = Field(..., ge=0, le=1)
    srv_diff_host_rate: float = Field(..., ge=0, le=1)
    dst_host_count: float = Field(..., ge=0)
    dst_host_srv_count: float = Field(..., ge=0)
    dst_host_same_srv_rate: float = Field(..., ge=0, le=1)
    dst_host_diff_srv_rate: float = Field(..., ge=0, le=1)
    dst_host_same_src_port_rate: float = Field(..., ge=0, le=1)
    dst_host_srv_diff_host_rate: float = Field(..., ge=0, le=1)
    dst_host_serror_rate: float = Field(..., ge=0, le=1)
    dst_host_srv_serror_rate: float = Field(..., ge=0, le=1)
    dst_host_rerror_rate: float = Field(..., ge=0, le=1)
    dst_host_srv_rerror_rate: float = Field(..., ge=0, le=1)

    @field_validator("protocol_type")
    @classmethod
    def _protocolo(cls, v: str) -> str:
        v = v.lower()
        if v not in {"tcp", "udp", "icmp"}:
            raise ValueError("protocol_type debe ser tcp, udp o icmp")
        return v

    @field_validator("service", "flag")
    @classmethod
    def _minusculas(cls, v: str) -> str:
        return v.lower()


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: FilaTrafico


MAX_POR_LOTE = 500


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # El límite vive aquí y no en el endpoint: así la petición desmedida se
    # rechaza con 422 en la validación, antes de construir la matriz de
    # características.
    items: list[PredictRequest] = Field(..., min_length=1, max_length=MAX_POR_LOTE)


class PredictResponse(BaseModel):
    id: int
    ts: str
    es_ataque: bool
    etiqueta: Literal["normal", "ataque"]
    clase: str
    probabilidad_ataque: float
    probabilidad_clase: float
    modelo: str
    version_modelo: str
    umbral: float
    origen: str
    alerta: str
    avisos: list[str] = []


class BatchResponse(BaseModel):
    total: int
    ataques: int
    resultados: list[PredictResponse]


class HistoryResponse(BaseModel):
    total: int
    almacen: dict
    predicciones: list[dict]


class HealthResponse(BaseModel):
    status: str
    servicio: str
    version: str
    modelos_disponibles: bool
    integridad_artefactos: bool
    modelo: list[str] | None
    version_modelo: str | None
    umbral_decision: float | None
    almacen: dict
    metricas: dict
