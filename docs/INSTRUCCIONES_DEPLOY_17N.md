# INSTRUCCIONES_DEPLOY_17N.md

El código ya está en GitHub (`final`, commit 700b55d) y Render ya desplegó esa
rama. Falta un paso que no se puede hacer desde el repositorio: actualizar las
variables de entorno del servicio, porque los `.joblib` no viajan en Git.

Síntoma confirmado el 17/11/2026 en `https://red-centinela-api.onrender.com/health`:

- `metricas.binario_kddtest.macro_f1` = 0.9251 (viene de Git, ya está bien).
- `umbral_decision` = 0.41 y `version_modelo` = 1.0.0 (vienen del paquete de
  modelos antiguo). Las predicciones siguen usando el umbral viejo.

Mientras esos dos números no concuerden, la defensa mostraría una cifra buena
junto a un comportamiento viejo. Hay que corregirlo.

## Opción A: sincronizar el Blueprint (la más corta)

`render.yaml` ya trae los valores nuevos para las tres variables que cambiaron.
En Render:

1. Entrar a https://dashboard.render.com y abrir el Blueprint de Red Centinela.
2. Pulsar **Sync Blueprint** (o **Apply blueprint changes**).
3. Esperar a que `red-centinela-api` termine de desplegar. El plan gratuito
   tarda alrededor de un minuto.

La sincronización respeta las variables marcadas como `sync: false`
(`DATABASE_URL` y el token de Telegram), así que no se pierden.

## Opción B: editar las variables a mano

En Render, servicio `red-centinela-api`, pestaña **Environment**, editar:

| Variable | Valor |
|---|---|
| `REDCENTINELA_MODELOS_URL` | `https://github.com/anorak1212/red-centinela/releases/download/modelos-v1.4.0/modelos_red_centinela.tar.gz` |
| `REDCENTINELA_MODELOS_SHA256` | `93573b577a0b982f4c32fe5bf4f579bbc74ee6b271af290f265237e5ed6067a7` |
| `REDCENTINELA_TABLERO_URL` | `https://red-centinela-k9gkhpyvsakean9cuhfd4n.streamlit.app` |

Guardar y lanzar **Manual Deploy > Deploy latest commit**.

## Verificación obligatoria después

Abrir `https://red-centinela-api.onrender.com/health` y comprobar los tres
puntos:

- `umbral_decision` = 0.01
- `version_modelo` = 1.3.0-fasec3
- `metricas.binario_kddtest.macro_f1` = 0.9251

Si el servicio está dormido, el primer acceso tarda unos 50 segundos. Si el
umbral sigue en 0.41, el build no descargó el paquete nuevo: revisar el log de
build y el valor del SHA antes de seguir.

Después, en el tablero, vista Sistema, el criterio PERF-003 debe aparecer como
cumplido y DEPLOY-013 debe dejar de decir "sin URL".

## Por qué no se hizo automáticamente

No hay sesión iniciada en Render en el navegador ni token de API de Render en
este entorno. Sin cualquiera de las dos cosas, cambiar variables de entorno no
es posible desde aquí. No se pidieron credenciales ni se intentó adivinarlas.
