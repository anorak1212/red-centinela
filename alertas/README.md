# Alertas (M5)

Envío de alertas por Telegram cuando el motor detecta tráfico malicioso.

## Diseño

- El servicio P3 recibe el evento de P2 y dispara la alerta de forma asíncrona (cola o tarea en segundo plano), para no sumar latencia al `p95` de `/predict`.
- Comunicación con el Bot API de Telegram por HTTP REST (`requests`), sin librerías adicionales.
- El token del bot entra solo por variable de entorno: prohibido en código (control que mitiga AM-10).

## Criterios

- TTR menor o igual a 60 segundos desde la detección.
- Al menos 95 % de entregas confirmadas por el API de Telegram (ALERT-010).

## Estado

Pendiente, corresponde al entregable E5 del cronograma.