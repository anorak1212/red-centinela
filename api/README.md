# API REST (M3)

Servicio FastAPI que expone el motor de detección.

## Endpoints

- `GET /health` : disponibilidad del servicio.
- `POST /predict` : recibe un vector de características y devuelve la clasificación.
- `GET /history` : historial de predicciones del tablero.

## Criterios

- Latencia p95 menor o igual a 200 ms en `/predict` y `/health`, medida con el modelo cargado (PERF-002).
- Validación estricta de la petición (OWASP API Top 10, requisito SEG-007): sin SQL por concatenación, credenciales solo por variables de entorno.
- Arranque: `uvicorn api.main:app --reload`.

## Estado

Pendiente, corresponde al entregable E3 del cronograma.