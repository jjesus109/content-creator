# ESPECIFICACIÓN TÉCNICA DEFINITIVA: CLAW-CHAT MULTI-AGENTE (TELEGRAM EDITION)

## 1. Visión General del Proyecto

Desarrollo de un asistente de IA multi-agente operado a través de Telegram (texto y notas de voz), diseñado para la ejecución autónoma de tareas y gestión de proyectos de software. El sistema utiliza **Gemini Flash** como orquestador cognitivo de baja latencia, **OpenClaw** desplegado en una **Raspberry Pi** como motor de ejecución local, y **Claude** (vía CLI local) como ingeniero de software bajo un esquema de *Spec-Driven Development*. Toda la telemetría está centralizada en **Better Stack**.

## 2. Arquitectura del Sistema y Componentes

### 2.1. Frontend y Capa de Transporte (Telegram)

- **Interfaz:** Bot de Telegram configurado vía *BotFather*.
- **Input del Usuario:** Texto plano (ej. vía dictado de Android Auto) o archivos de audio nativos de Telegram (`.ogg` / Opus).
- **Conectividad:** *Webhooks* configurados hacia el backend. Se abandona la arquitectura WebSocket en favor de peticiones HTTP asíncronas para una mayor resiliencia y menor consumo de recursos.

### 2.2. Backend / API Gateway (FastAPI)

- **Rol:** *Webhook receiver* y enrutador principal. Maneja la validación de seguridad (asegurando que solo tu `chat_id` pueda interactuar con el bot).
- **Procesamiento:** Recibe los payloads de Telegram, extrae el texto o descarga temporalmente los audios `.ogg` y los transfiere a las capas inferiores.

### 2.3. Capa de Cognición y Toma de Decisiones (Gemini Flash)

- **Rol:** Clasificación de *intents*, extracción de contexto y planificación de ejecución.
- **Procesamiento Multimodal:** Recibe el audio `.ogg` directamente de Telegram (sin necesidad de un servicio STT intermedio) o el texto. Retorna un JSON estructurado definiendo si es una respuesta conversacional o una invocación de herramientas para OpenClaw.

### 2.4. Motor de Ejecución Autónoma (OpenClaw en Raspberry Pi)

- **Rol:** Ejecutor local (*Agentic Actor*). Recibe el plan de Gemini y utiliza sus herramientas (Terminal, File System) para accionar.
- **Infraestructura:** Servicio `systemd` en Raspberry Pi. Entorno de ejecución de código aislado mediante Docker.

### 2.5. Capa de Desarrollo (Claude vía SDD CLI)

- **Rol:** Generación de especificaciones y escritura de código.
- **Integración:** Invocado localmente por OpenClaw mediante el comando de tu framework (ej. `sdd-cli run`). OpenClaw intercepta la salida estándar y de error para retroalimentar al usuario.

### 2.6. Capa de Observabilidad (Better Stack)

- **Rol:** Ingesta asíncrona de logs y trazas LLM sin bloquear el *event loop* de FastAPI.

## 3. Flujo de Datos Asíncrono

1. **Ingreso:** Envías una nota de voz por Telegram: *"Inicia el backend del proyecto X y crea la base de datos"*.
2. **Recepción:** El webhook de FastAPI recibe la actualización de Telegram, valida tu `user_id` y descarga el archivo `.ogg`.
3. **Cognición:** FastAPI envía el `.ogg` a Gemini Flash. Gemini determina que es un comando de desarrollo y emite un JSON estructurado de acción.
4. **Ejecución (OpenClaw):** FastAPI despacha la acción a OpenClaw en la Raspberry Pi.
5. **Desarrollo (Claude):** OpenClaw abre la terminal en el directorio correcto y ejecuta tu framework SDD: `sdd-cli generate --context "backend proyecto X..."`.
6. **Streaming de Feedback:** Mientras Claude trabaja localmente, OpenClaw captura los *logs* del proceso y envía actualizaciones periódicas a FastAPI, que a su vez te envía mensajes de Telegram (ej. *"⚙️ Claude ha generado los esquemas de la DB..."*).
7. **Finalización y Telemetría:** Se escriben los archivos en disco, se notifica el éxito por Telegram y todos los eventos del ciclo (latencia, tokens, comandos Bash) se envían a Better Stack de forma estructurada.

## 4. Especificación de Módulos (Para el Framework SDD)

Aporta estos módulos como directivas a tu framework para la generación iterativa:

### Módulo 1: `telegram-webhook-gateway` (Backend)

- **Responsabilidad:** Exponer el endpoint `/webhook` para Telegram, verificar la firma de los mensajes, implementar la lista blanca de `user_ids` autorizados y gestionar la descarga temporal de archivos multimedia.
- **Salida:** Evento normalizado interno (Texto o Path de archivo de audio) listo para el orquestador.

### Módulo 2: `gemini-intent-router` (Cognición)

- **Responsabilidad:** Empaquetar el input del usuario en un *prompt* multimodal para la API de Gemini Flash. Debe incluir instrucciones de sistema (System Prompt) que definan estrictamente la estructura JSON de salida esperada (ej. `{"action": "chat", "reply": "..."}` vs `{"action": "execute", "target_agent": "openclaw", "payload": "..."}`).

### Módulo 3: `openclaw-local-operator` (Raspberry Pi)

- **Responsabilidad:** Servicio en Python/Node que expone una API interna (o se conecta vía long-polling a tu servidor si no tienes IP pública) para recibir los comandos de ejecución.
- **Skills:** Manipulación de directorios, ejecución de `subprocess` con captura de `stdout/stderr` en tiempo real.

### Módulo 4: `claude-sdd-bridge` (Integración de Desarrollo)

- **Responsabilidad:** Sub-módulo de OpenClaw diseñado para orquestar tu CLI local. Debe formatear los argumentos correctamente y manejar los códigos de salida (exit codes) del CLI para determinar si la generación de código fue exitosa o falló.

### Módulo 5: `betterstack-async-telemetry` (Observabilidad)

- **Responsabilidad:** Wrapper del cliente `logtail-python`. Debe implementarse de manera global utilizando `contextvars` para rastrear un `trace_id` único desde que entra el mensaje de Telegram hasta que OpenClaw finaliza la tarea. Todas las escrituras de logs deben ser enviadas a colas en segundo plano.

## 5. Requerimientos de Seguridad Críticos

- **Autenticación Hardcoded:** El bot de Telegram no responderá a nadie que no esté en el array `ALLOWED_TELEGRAM_USERS`. Cualquier intento de acceso no autorizado será logueado en Better Stack con nivel `WARNING`.
- **Docker Sandboxing:** OpenClaw ejecutará los scripts generados por Claude (como pruebas unitarias o scripts bash autónomos) dentro de un contenedor Docker efímero en la Raspberry Pi, montando únicamente el directorio del proyecto correspondiente.

## 6. Roadmap de Implementación (Fases de Desarrollo)

Para mantener el control y asegurar la calidad del código, el proyecto se dividirá en 5 fases de despliegue usando tu framework SDD:

- **Fase 1: Infraestructura de Mensajería.** Configuración del Bot de Telegram, creación del webhook en FastAPI (o *long-polling* para pruebas locales) y validación estricta de seguridad. El bot debe poder recibir mensajes y hacer "eco".
- **Fase 2: Cognición Multimodal.** Integración del SDK de Google GenAI. FastAPI procesa notas de voz `.ogg` de Telegram, las envía a Gemini Flash y retorna el análisis o respuesta en formato texto por Telegram.
- **Fase 3: Ejecución Autónoma Base (OpenClaw).** Configuración del entorno en la Raspberry Pi (`systemd`). Creación de la capa de comunicación entre FastAPI y OpenClaw. Implementación de comandos básicos del sistema (listar archivos, leer estado de recursos).
- **Fase 4: Orquestación Multi-Agente (Claude CLI).** Implementación del puente para que OpenClaw ejecute comandos del framework SDD local. Captura de *logs* de terminal y envío de actualizaciones de estado ("typing..." o mensajes parciales) hacia Telegram.
- **Fase 5: Telemetría de Producción.** Integración global de Better Stack. Refactorización de todos los `print()` y logs estándar para usar el esquema JSON estructurado con `trace_ids`. Ingesta de métricas de uso de tokens y tiempos de respuesta.

