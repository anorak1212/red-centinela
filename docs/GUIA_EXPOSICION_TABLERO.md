# Guía detallada del tablero Red Centinela (para exponer)

Guía de referencia para explicar **qué hace cada pantalla, pestaña, botón, control y elemento** del tablero Streamlit. Está basada en el comportamiento actual del código del repositorio (`tablero/`, rama `final`). 

> Nota: algunas mejoras recientes (vista **Sistema** con verificación medida y el desglose **ataques sin familia** en **Resumen**) están en el repositorio pero pueden no estar desplegadas en producción hasta que se publique esa versión.

---

## 1. Acceso y estructura general

### 1.1 Pantalla de inicio de sesión (`tablero/app.py`, `tablero/auth.py`)
Se muestra solo si hay usuarios configurados en la variable `REDCENTINELA_TABLERO_USUARIOS`. Si no está configurada, el acceso es abierto.

- **Marca/título:** “Red Centinela” y versión del tablero.
- **Formulario “Iniciar sesión”** (bloque con borde):
  - **Usuario**: campo de texto (autocompletado de usuario).
  - **Contraseña**: campo oculto.
  - **Botón “Entrar”** (primario, con icono de login): valida credenciales.
    - Si son correctas: inicia sesión y recarga la app.
    - Si son incorrectas: muestra error “Usuario o contraseña incorrectos.” y registra un fallo.
- **Bloqueo por intentos:** tras varios intentos fallidos (`INTENTOS_MAXIMOS`) el acceso se bloquea por un tiempo (`BLOQUEO_SEGUNDOS`) y el botón se deshabilita mostrando “Demasiados intentos fallidos…”.
- **Texto informativo:** indica intentos permitidos, tiempo de bloqueo y duración de sesión (`SESION_HORAS`).
- **Roles (concepto):** `admin` (puede predecir/escribir acciones que registran historial) y `lector` (solo lectura; no puede predecir). La sesión guarda nombre, rol y si la contraseña está en texto plano (aviso para usar hash con `python -m tablero.auth`).

### 1.2 Barra lateral (visible tras iniciar sesión o en acceso abierto)
La barra lateral es el panel de control global. Se oculta en la pantalla de login.

- **Marca:** logo/nombre y versión.
- **Menú de navegación** (secciones y páginas, `tablero/navegacion.py`):
  - **Operación:** *Resumen* (por defecto), *Analizar*, *Historial*.
  - **Modelo:** *Modelo y métricas*.
  - **Proyecto:** *Sistema*, *Ayuda*.
  - **Ajustes:** *Configuración*.
  - Cada elemento es un enlace de página (`st.page_link`) que cambia la vista.
- **Controles rápidos (recorrido y presentación, `tablero/guia.py`):**
  - **Interruptor “Recorrido de la demo”**: activa/desactiva el guion guiado de 7 pasos (aparece un panel arriba de la vista). Al cambiar de estado reinicia/guarda el paso y recarga.
  - **Interruptor “Modo presentación”**: activa letra más grande y menos texto secundario (útil para proyectar). Se guarda en preferencias de la sesión y recarga.
- **Sección “Conexión con la API”** (expansor; se abre solo si no hay conexión):
  - **URL de la API** (campo de texto): por defecto `REDCENTINELA_API` o `http://127.0.0.1:8000`. Si se cambia, actualiza la sesión, limpia latencia/cache y recarga.
  - **Botón “Comprobar conexión”** (primario): invalida caché, sondea `/health` (hasta ~20 s), mide latencia y muestra éxito/error. Si responde, guarda la latencia medida.
  - **Botón “Despertar servicio”**: sondea `/health` hasta ~90 s (útil con Render en plan gratuito, que se duerme). Muestra si despertó y en cuántos segundos, o error.
- **Tarjeta de conexión:** muestra estado de la API/URL y la latencia medida (si existe).
- **Botón “Recargar datos”**: vacía la caché de datos del tablero y vuelve a pedir todo a la API (recarga).
- **Texto de caché:** indica que los datos vienen de la API (no de la sesión local del tablero) y los TTL: 10 s para historial/estado, 5 min para métricas.
- **Bloque de sesión:**
  - Si acceso abierto: aviso de que definiendo `REDCENTINELA_TABLERO_USUARIOS` se exige login.
  - Si hay sesión: muestra usuario y rol, botón **“Salir”** (cierra sesión y recarga) y, si aplica, advertencia si la contraseña está en texto plano.

### 1.3 Recorrido guiado de la demo (panel superior, `tablero/guia.py`)
Visible cuando “Recorrido de la demo” está activo. Guion de 7 pasos; **“Siguiente/Anterior”** cambian de vista automáticamente (`st.switch_page`).

- **Cabecera del paso:** número de paso (1–7), título, acción a realizar y “guion” (qué decir).
- **Botón “Anterior”**: va al paso previo (deshabilitado en el primero).
- **Botón “Siguiente”** (primario): avanza al siguiente paso y navega a su vista (en el último paso se reemplaza por **“Terminar”**).
- **Botón “Terminar”** (último paso): desactiva el recorrido y lo reinicia.
- **Botón “Ir a \<Vista\>”**: aparece si no estás en la vista del paso; navega a ella.

**Pasos del guion:**
1. **Resumen** — “El servicio está vivo y se mide”: portada y panorama; mencionar macro-F1 0.9251 frente a la meta de 0.90 sobre 22,544 filas no vistas, y decir que el umbral se recalibró con validación de familias no vistas, no contra el test.
2. **Analizar** — “Una conexión, una decisión”: predecir fila DoS y luego R2L; DoS se detecta bien, R2L muestra el límite.
3. **Analizar** — “Un lote con verdad conocida”: en CSV descargar muestra etiquetada, subirla y predecir 150 filas; la matriz separa detección de clasificación.
4. **Historial** — “La memoria del sistema”: filtrar por clase y usar simulador de umbral; bajar umbral atrapa más ataques con más falsas alarmas.
5. **Modelo y métricas** — “Lo que interroga el jurado”: alternar matriz KDDTest+ / KDDTest-21; que baje en el subconjunto difícil indica evaluación honesta.
6. **Sistema** — “Qué existe y qué falta”: verificar y recorrer criterios con cifras/veredictos (incluidos los no cumplidos).
7. **Resumen** — “El cierre”: descargar el reporte para la defensa.

### 1.4 Principios de interacción (transversales)
- **Fuente de datos:** el tablero solo consume la API REST (no carga modelos ni abre la BD). Si la API no responde, muchas vistas muestran aviso y limitan acciones.
- **Modo degradado:** si la API responde sin modelos/artefactos disponibles, se avisa y los controles de predicción se deshabilitan (`/predict` devolvería 503).
- **Permisos:** si el rol es lector, las acciones que escriben (predecir/análisis que se guarda) se bloquean con aviso “sin permiso para predecir…”.
- **Caché:** lecturas cacheadas (10 s estado/historial, 5 min métricas); “Recargar datos” o acciones que invalidan fuerzan nueva lectura.

---

## 2. Vistas (páginas) y sus elementos

## 2.1 Resumen (`tablero/vistas/resumen.py`)
**Qué es:** panorama operativo del servicio, tráfico analizado, alertas y panorama del modelo. Es la “portada” de la demo.

**Si la API no responde:** bloque “La API no responde” y se detiene.

**Encabezado:** “Resumen operativo” — indica que las cifras vienen de `/history/resumen` y `/metrics`, no de la sesión.

**Banda superior (KPIs principales):**
- Predicciones (total del historial persistido en la API).
- Ataques (`es_ataque = verdadero`): muestra total y, en la versión con B2, desglose **con familia** y **sin familia clasificada**.
- Tasa de ataque (% sobre total).
- Familias detectadas (de 4 familias de ataque: dos, probe, r2l, u2r).
- Macro-F1 (KDDTest+, meta 0.90). Tono “sano” si el servicio está ok.

**Avisos:** modo degradado si aplica.

**Sección 1 — “Panorama del modelo” (cifras y gráfico):**
- Texto explicativo: referencia a KDDTest+ (22,544 registros no vistos) y que no se ajustó contra él.
- **Indicadores de modelo:** Macro-F1 binario, AUC ROC, Precisión de ataque, Recall de ataque, Macro-F1 cinco clases, Ataques en la prueba.
- **Gráfica “radar”/mapa de métricas:** compara capacidades (binaria, separación, precisión, recall, 5 clases, subconjunto difícil) y anota la meta de macro-F1.
- **Nota al pie:** origen `motor/models/metrics.json` servido por `/metrics`, y puntualizaciones (precisión ≠ alarmas ciertas en todo contexto, diferencia detección vs clasificación de familias difíciles).

**Sección 2 — “Estado del servicio”:**
- **Indicadores:** API (en línea/degradada/sin respuesta), Integridad (SHA-256 íntegro/sin verificar), Modelos (disponibles/no cargados), Almacén (motor, persistente/no persistente y nota), Generado (fecha de métricas), Conjunto difícil (macro-F1 KDDTest-21).

**Sección 3 — “Actividad registrada”:**
- **Izquierda:** gráfico de barras horizontales del histórico por clase (normal, dos, probe, r2l, u2r).
- **Derecha:** tarjeta “Telegram” (configurado/no configurado, enviados, fallidos, en cola, último envío exitoso o último error) y, si no hay historial, texto orientativo.
- **Bloque explicativo (si hay ataques sin familia, B2):** explica por qué “ataques” no cuadra con la suma de familias: la cabeza binaria marcó ataque pero la multiclase no reconoció familia (clase queda como normal) — típico en r2l/u2r no vistas; el historial no se reescribe.

**Sección 4 — “Composición por clase”:**
- Gráfica de dona con distribución del historial completo por familia predicha.
- Nota sobre r2l/u2r (bajo recall/soporte) y remite a “Modelo y métricas”.

**Sección 5 — “Postura reciente” (últimas 50 predicciones):**
- **Indicadores:** Actividad hostil (alta/media/baja según % de ataques), Familia dominante (la más frecuente entre ataques recientes; si ataques recientes sin familia, lo indica), Último ataque, Alertas confirmadas.
- **Tabla:** últimas 5 predicciones (ID, hora UTC, origen, clase, p(ataque)).

**Sección 6 — “Reporte para la defensa”:**
- **Botón de descarga “Reporte de la defensa (Markdown)”**: genera en vivo un `.md` con estado del servicio, métricas (binario, 5 clases, familias, criterios) e historial agregado/reciente. Útil como evidencia impresa o anexo.
- Nota: si la API no responde, el reporte sale con lo disponible.

## 2.2 Analizar (`tablero/vistas/analizar.py`)
**Qué es:** enviar tráfico a predecir. **Cada análisis se guarda en el historial** y, si es ataque y hay bot, puede disparar alerta. No es “modo prueba”.

**Precondiciones/bloqueos:**
- Sin API: bloquea y no permite predecir.
- Modo degradado (sin modelos): deshabilita predicción.
- Rol sin permiso de escritura (lector): deshabilita predicción con aviso.

**Dos pestañas:**

### Pestaña A — “Conexión individual” (una fila → `/predict`)
- **Selector “Fila de partida”** (si existe `datasets/sample_etiquetado.csv`): ejemplos reales de KDDTest+ por familia (normal, dos, probe, r2l, u2r). Si falta el archivo, permite entrada manual y muestra aviso.
- **Selector de modo “Formulario guiado” / “JSON completo”:**
  - *Formulario guiado:* edita campos clave y mantiene las otras 33 características de la fila base.
    - **Protocolo** (tcp/udp/icmp), **Servicio** (texto), **Flag** (SF, S0, REJ, etc.).
    - **Campos numéricos clave:** duración, bytes origen→destino, bytes destino→origen, `count`, `srv_count`, `serror_rate`, `same_srv_rate`, `dst_host_count`.
  - *JSON completo:* área de texto con las **41 columnas** en JSON editable.
- **Botón “Predecir”** (primario): envía a `/predict`.
  - Valida JSON (en modo JSON) y que existan las 41 columnas.
  - Muestra spinner “Consultando la API…”.
  - **Resultado:** banda verde/roja según normal/ataque con cifras (p(ataque), clase y confianza p(clase), umbral, ID en historial) y mensaje de qué ocurrió (registro guardado; alerta si aplica).
  - **Barra/medidor de probabilidad:** `p(ataque)` frente al umbral.
  - **Avisos:** si la API devuelve avisos (p. ej. categorías no vistas), se muestran.
  - **Comparación con etiqueta real** (si se partió de ejemplo etiquetado): indica si coincide o no con la familia real.
- **Nota:** al lado del botón recuerda la etiqueta real de la fila elegida (útil en demo).

### Pestaña B — “Archivo CSV” (lote → `/predict/batch`)
- **Explicación:** el CSV debe traer las 41 columnas del NSL-KDD; si incluye `label` o `family`, se compara con la verdad.
- **Carga de archivo:** “Archivo CSV” (`.csv`).
- **Botones de ayuda/descarga:**
  - **“Plantilla vacía (41 columnas)”**: descarga CSV con encabezados.
  - **“Muestra etiquetada (150 filas)”** (si existe): descarga muestra con columna `family`.
- **Validación/lectura:** hasta 2,000 filas por carga; rechaza si faltan columnas o hay errores (muestra mensaje). Se eliminan temporales.
- **KPIs previos:** filas válidas, cuántas traen etiqueta real, tamaño máximo por carga y tamaño de lote por petición.
- **Botón “Predecir N filas”** (primario): envía en lotes (tamaño configurable) a `/predict/batch`.
  - **Barra de progreso** por porcentaje/lotes.
  - Al terminar: guarda resultados en sesión, invalida caché y muestra éxito.
- **Resultados del lote (si existen):**
  - **KPIs:** analizadas, ataques, normales, proporción.
  - **Gráfico de barras:** distribución del lote por clase predicha.
  - **“Detección real”** (si hay `family`): tabla por familia real con conteos de *detección* (marcado ataque) y *familia correcta*; bloque que explica la diferencia entre detectar y clasificar.
  - **Matriz de confusión del lote** (si hay verdad): filas = familia real, columnas = decisión de la API (normal si no superó umbral, o clase predicha).
  - **Detalle:**
    - **Interruptor “Solo ataques”**: filtra la tabla a filas con `es_ataque`.
    - **Tabla de registros** (ID, es_ataque, etiqueta, clase, p(ataque) con barra, p(clase), y `real` si aplica).
  - **Botón “Descargar resultados (CSV)”**: exporta el detalle del lote.

## 2.3 Historial (`tablero/vistas/historial.py`)
**Qué es:** memoria del sistema; todo lo analizado y guardado por la API, con filtros y análisis sobre probabilidades ya registradas.

**Controles (bloque de filtros):**
- **Registros leídos** (100, 250, 500): cuántos pide a `/history` (máx. 500 por consulta).
- **Origen**: todos / `api` (individual) / `api-lote`.
- **Clases** (multiselección): normal, dos, probe, r2l, u2r.
- **Botón “Actualizar”**: invalida caché y relee.
- **Slider “p(ataque) entre”**: rango 0.0–1.0.
- **Buscar ID**: filtra por ID exacto (entero).
- **Interruptor “Solo con alerta enviada”**: registros con `alerta_enviada` verdadera.

**Banda de resumen del filtrado:** registros tras filtro, ataques, tasa, alertas enviadas confirmadas, clases distintas.

**Sección 1 — “Probabilidad de ataque en el tiempo”:** serie temporal de p(ataque) con marca del umbral de decisión (si disponible).

**Sección 2 — “Distribución”:** barras por clase y por origen (con nota interpretativa).

**Sección 3 — “Simulador de umbral” (cálculo local, no cambia la API):**
- **Slider “Umbral simulado”** (0.05–0.95).
- **KPIs:** ataques con umbral real, ataques con umbral simulado, cuántos pasarían a ataque, cuántos pasarían a normal.
- **Histograma de probabilidades** con umbral real y simulado.
- **Aclaración:** recuenta p(ataque) guardadas; sin etiquetas reales no dice si acierta más, solo cuántas decisiones se moverían. El umbral oficial se calibró en holdout interno.

**Sección 4 — “Registros”:**
- Tabla (hasta 60 más recientes) con ID, hora UTC, origen, clase, p(ataque), p(clase), modelo, alerta (sí/no).
- **Expansor “Ver las 41 características de un registro”**: selector de ID y visualización JSON de `features`.
- **Botón “Descargar CSV (sin características)”** y **“Descargar JSON (con características)”** del conjunto filtrado.

## 2.4 Modelo y métricas (`tablero/vistas/modelo.py`)
**Qué es:** cifras del modelo publicadas por `/metrics` (desde `motor/models/metrics.json`), evaluadas sobre KDDTest+ y KDDTest-21 (datos no vistos en entrenamiento). Vista para preguntas técnicas del jurado.

**Banda inicial:** versión, fecha de generación, umbral (0.01 en la versión vigente; 0.41 era el baseline) y KPIs (macro-F1 binario, F1 ponderado, AUC ROC, macro-F1 5 clases, macro-F1 KDDTest-21). Si el tablero sigue mostrando otro umbral, está sirviendo artefactos viejos: decirlo en voz alta en vez de improvisar.

**Sección 1 — “Cabeza binaria: normal contra ataque”:**
- **Selector “Conjunto evaluado”**: KDDTest+ / KDDTest-21 (cambia matriz y cifras mostradas).
- KPIs: Macro-F1, Exactitud, Precisión de ataque, Recall de ataque, AUC ROC, Ataques reales.
- **Matriz de confusión** (normal/ataque) y tabla con VN, FP, FN, VP e interpretación (falsos negativos = error caro; precisión alta/recall moderado).

**Sección 2 — “Cinco clases: qué familia es el ataque”:**
- Tabla por clase (normal, dos, probe, r2l, u2r): Precisión, Recall, F1, Soporte.
- Barras de F1 por clase y **matriz de confusión 5×5** (fila real, columna predicha). Nota: r2l/u2r son el techo difícil.

**Sección 3 — “Detección contra clasificación”:**
- Gráfico comparando, por familia de ataque, **recall de detección** (“dijo ataque”) vs **recall de clasificación** (“acertó la familia”).
- KPIs por familia y bloque explicando por qué r2l falla (variantes no vistas en entrenamiento).

**Sección 4 — “KDDTest-21: el subconjunto difícil”:**
- KPIs y tabla comparativa KDDTest+ vs KDDTest-21. Explica que si no bajara habría sospecha de fuga; aquí baja.

**Sección 5 — “Comparativa de modelos”** (si existe en métricas): tabla/gráfico de modelos comparados (no desplegados) y advertencia de que no son comparables 1:1 con producción por submuestras/condiciones.

**Sección 6 — “Holdout interno e Isolation Forest”:**
- **Holdout interno:** macro-F1 binario/multiclase en la misma distribución del entrenamiento. **No cumple PERF-003** ni prueba generalización (se muestra por transparencia).
- **Isolation Forest (no supervisado):** AUC ROC y recall en el 10% más anómalo; entrenado solo con tráfico normal, **ordena rareza, no decide etiqueta**.

**Sección 7 — “Costo computacional y artefactos”:** latencia por fila y en lote, tiempos de entrenamiento, modelo/cabezas/umbral en producción y nota de medición.

## 2.5 Sistema (`tablero/vistas/sistema.py`)
**Qué es:** verificación medida del sistema (M1–M6), criterios y superficie de la API. En la versión actual, **cada indicador sale de una medición hecha en el momento** (no es texto fijo).

**Controles superiores:**
- **Expansor “Ajustes de la verificación”:**
  - **URL pública del tablero** (texto, por defecto `REDCENTINELA_TABLERO_URL`): vacía implica que DEPLOY-013 no se puede comprobar.
  - **Muestras de latencia de /predict** (1–20, por defecto 10): cada muestra hace una petición de predicción con una fila normal y **escribe una fila en el historial**. Antes de medir se hace una llamada de calentamiento que se descarta: la primera predicción tras un arranque en frío carga el .joblib. Si la API envía la cabecera Server-Timing, el p95 que se compara contra el umbral es el del cómputo del servidor y la ida y vuelta se muestra aparte.
- **Botón “Volver a verificar”** (primario): vuelve a medir todo.
- Estado de servicio y, si despertó tras espera, mensaje con segundos.

**Comportamiento de medición:**
- Mide `/health`, `/metrics`, `/alertas/estado`, endpoints GET de lectura, URL del tablero (sondeo sin seguir redirecciones) y latencia de `/predict`. Inspecciona datasets versionados para M1.
- Si la API es pública y no responde al inicio, puede esperar a que despierte (hasta ~45 s) y repetir.

**Si la API no responde:** bloque indicando que módulos/criterios quedan “no verificados” (no “falla” definitiva) hasta que conteste.

**Banda “Sistema medido”:** momento de medición, módulos/criterios comprobados, contadores (módulos operando, endpoints 200, integridad, umbral, macro-F1).

**Sección 1 — “Módulos del alcance” (M1–M6):** estado por módulo con motivo (OPERANDO / FALLA / NO VERIFICADO). M1: datasets versionados; M2: modelos/integridad; M3: API+almacén/endpoints; M4: URL del tablero (p. ej. 303 a login = responde pero acceso público se juzga aparte); M5: alertas Telegram (configurado/envíos confirmados); M6: despliegue público y persistencia.

**Sección 2 — “Criterios y veredicto”:** tabla con criterio, exigencia, medido, veredicto (cumplido/no cumplido/no verificado) y motivo. Incluye integridad SHA-256, PERF-003 (macro-F1 vs meta 0.90), PERF-006 (latencia p95, medida en vivo), ALERT-010 (envío confirmado), DEPLOY-013 (URL pública API+tablero).

**Sección 3 — “Superficie de la API”:** 8 endpoints con método, ruta, propósito y medición. Los POST no se sondean (escriben/envían).

**Sección 4 — “Lo que esta vista no puede medir”:** video demo, ensayo con jurado y decisión del profesor sobre PERF-003 no son verificables por código (pendientes de calendario).

## 2.6 Ayuda (`tablero/vistas/ayuda.py`)
**Qué es:** cómo ejecutar, contrato de la API y límites/definiciones.

**Pestaña “Cómo se ejecuta”:**
- Comandos locales (`python -m cli serve`, `python -m cli estado`, `streamlit run tablero/app.py`).
- Comandos de pruebas/smoke.
- Nota de despliegue (API y tablero como servicios separados) y botón “Despertar servicio”.
- Si hay conexión: JSON con servicio conectado (api, versión, modelo, versión_modelo, umbral, integridad, almacén).

**Pestaña “Contrato de la API”:**
- Tabla de endpoints (GET/POST) y su propósito.
- Tabla de variables de entorno (DATABASE_URL, REDCENTINELA_DB, TELEGRAM, REDCENTINELA_API, REDCENTINELA_TABLERO_USUARIOS, rate limit, etc.).
- Nota: nombres de endpoints fijados por diseño (E14/FUN).

**Pestaña “Límites y decisiones”:**
- **Glosario** (buscador por término/definición): Macro-F1, Recall/Precisión de ataque, Umbral, KDDTest+, AUC ROC, KDDTest-21, Detección vs clasificación, Isolation Forest, Modo degradado.
- Bloques: “Lo que el sistema no hace” (no IDS en tiempo real, no detección de cero-day por nombre; r2l/u2r con números a la vista) y principios de UX (controles se deshabilitan si no aplican).
- **Código de color:** azul marca/acciones, verde azulado normal/cumplido, ámbar umbral/atención, rojo ataque/incumplido.

## 2.7 Configuración (`tablero/vistas/configuracion.py`)
**Qué es:** preferencias del tablero (sesión del navegador). No cambia la API ni el umbral del modelo.

**Pestaña “Apariencia”:**
- **Tema** (claro/oscuro).
- **Color de acento** (marca/botones/barras; los colores de estado no cambian).
- **Densidad** (compacta/normal).
- **Animaciones** (on/off).
- **Modo presentación** (letra grande, menos notas; también en barra lateral).
- **Vista previa** de colores de estado y acento.

**Pestaña “Comportamiento”:**
- **Actualización automática del Resumen** (intervalo en segundos, cuando se activa en Resumen).
- **Registros que abre Historial** (100/250/500).
- **Filas por petición al analizar un CSV** (tamaño de lote).
- **Botón “Vaciar caché de datos”**: fuerza releer desde la API.
- Nota: umbral/endpoints/métricas no se configuran aquí (umbral simulado está en Historial).

**Pestaña “Conexión y sesión”:**
- Datos de API (URL, versión del tablero, timeout) y nota de dónde cambiar la URL.
- Sesión: acceso abierto o usuario/rol/si puede predecir/duración.

**Sección “Resumen de la configuración”:** indicadores de lo activo, **“Restablecer valores”** y **“Exportar configuración”** (JSON).

---

## 3. Conceptos y números clave para la exposición

- **Dataset:** NSL-KDD; evaluación honesta en **KDDTest+** (22,544 filas no vistas, con familias/variantes no presentes en entrenamiento) y **KDDTest-21** (subconjunto difícil).
- **Modelo en producción:** Random Forest de dos cabezas (binaria normal/ataque y multiclase 5 clases: normal, dos, probe, r2l, u2r) + Isolation Forest de apoyo (no supervisado, rareza, no decide etiqueta).
- **Línea base (v1.0.0, umbral 0.41):** macro-F1 binario 0.7995, AUC 0.9616, recall ataque 0.6698, macro-F1 5 clases 0.4716. Sirve para explicar de dónde se partió, no para citar el resultado actual.
- **Versión vigente (1.3.0-fasec3, umbral recalibrado a 0.01):** macro-F1 binario **0.9251**, exactitud 0.9279, precisión de ataque 0.8986, recall 0.9845, AUC 0.9641, macro-F1 binario en KDDTest-21 0.7496. Macro-F1 5 clases 0.5541, sin cambios. PERF-003 se cumple en la cabeza binaria; la multiclase sigue siendo limitación conocida.
- **Si preguntan por el precio:** bajar el umbral multiplica los falsos positivos por casi cuatro (de 285 a 1,058 sobre 9,711 normales). Se aceptó porque la métrica del proyecto es macro-F1 y porque el criterio se eligió antes de mirar KDDTest+. Curva completa en `docs/SENSIBILIDAD_UMBRAL.md`.
- **Detección vs clasificación:** detectar = marcar ataque (aunque se equivoque la familia); clasificar = acertar la familia. Se reportan por separado.
- **Umbral:** punto de corte sobre p(ataque), recalibrado con `leave-one-family-out` sobre KDDTrain+ (no en KDDTest+). El simulador de Historial solo recuenta decisiones sobre probabilidades guardadas.
- **Almacén:** local puede ser SQLite (no persistente en Render); producción usa PostgreSQL (Neon, persistente).
- **Artefactos:** modelos `.joblib` con integridad verificada por SHA-256 (manifiesto).

---

## 4. “Truco” rápido para recorrer la demo
1. Barra lateral: **Comprobar conexión** / **Despertar servicio** si hace falta.  
2. **Resumen**: panorama y KPIs.  
3. **Analizar → Conexión individual**: predecir ejemplo DoS y luego R2L; comparar etiqueta real.  
4. **Analizar → Archivo CSV**: subir muestra etiquetada y mostrar matriz del lote.  
5. **Historial**: filtros y **simulador de umbral**.  
6. **Modelo y métricas**: KDDTest+ vs KDDTest-21, familias r2l/u2r, holdout (no es cumplimiento).  
7. **Sistema**: **Volver a verificar** y explicar criterios/lo no medible.  
8. **Resumen**: descargar reporte.
