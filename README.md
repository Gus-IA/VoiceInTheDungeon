# 🏰 Voice in the Dungeon

** Proyecto realizado completamente usando vibe coding**

**Voice in the Dungeon** es una aventura de rol (RPG) controlada íntegramente por voz, donde la narrativa y el mundo se generan en tiempo real gracias a la Inteligencia Artificial.

🎮 **[¡Pruébalo aquí!](https://voice-in-the-dungeon.onrender.com/)**

![Licencia](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9+-bold.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green.svg)
![Groq](https://img.shields.io/badge/AI-Groq%20Llama%203.1-orange.svg)

## 🌟 Características Principales

-   **Control por Voz Total**: Interactúa con el mundo hablando naturalmente. El sistema utiliza **Whisper (via Groq)** para una transcripción ultra rápida.
-   **Generación de Mundo Procedimental**: Cada habitación, descripción y desafío es generado dinámicamente por un LLM (**Llama 3.1**), garantizando que ninguna partida sea igual a la anterior.
-   **Narrador Dinámico**: El juego te responde con voz propia utilizando la API de síntesis de voz del navegador.
-   **Memoria a Largo Plazo (RAG-lite)**: Un sistema de diario registra tus hazañas pasadas, permitiendo que la IA recuerde eventos clave de la partida incluso después de muchas horas de juego.
-   **Interfaz Inmersiva**: Incluye un minimapa dinámico, registro de acciones y un diseño oscuro y gótico para una inmersión total.

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
| :--- | :--- |
| **Backend** | Python 3.9+ / FastAPI |
| **Frontend** | Vanilla JS / TypeScript / CSS Moderno |
| **IA (Cerebro)** | Groq API (Llama 3.1 70B) |
| **IA (Voz)** | Whisper-large-v3 (Transcripción) |
| **Base de Datos** | PostgreSQL (Producción en Neon.tech) / SQLite (Local) |
| **Despliegue** | Docker / Render.com |

## 📐 Arquitectura y Funcionamiento

El flujo del juego es el siguiente:
1.  **Entrada de Audio**: El cliente captura el audio del usuario y lo envía al servidor.
2.  **Transcripción**: Groq (Whisper) convierte el audio a texto.
3.  **Procesamiento de Comandos**: Un LLM analiza la intención del jugador (moverse, coger objeto, atacar) y devuelve un JSON estructurado.
4.  **Estado del Juego**: El servidor mantiene el estado del jugador (inventario, salud, posición) en la base de datos.
5.  **Generación de Escenario**: Si el jugador entra en una nueva sala, el LLM genera la descripción y los objetos basándose en el contexto previo.
6.  **Memoria (Diario)**: Las acciones clave se guardan en un `journal` que se inyecta en el prompt del LLM para mantener la coherencia narrativa.

## 🚀 Despliegue en la Nube (Render + Neon)

Este proyecto está preparado para ser desplegado en **Render** con persistencia total de datos:

1.  **Base de Datos**: Usa **Neon.tech** para una DB de PostgreSQL gratuita y escalable.
2.  **Render Blueprint**: El archivo `render.yaml` pre-configura todo el entorno.
3.  **Variables de Entorno Necesarias**:
    *   `GROQ_API_KEY`: Tu clave de API de Groq Cloud.
    *   `DATABASE_URL`: URL de conexión de Postgres (ej. `postgres://user:pass@host/db?sslmode=require`).
    *   `JWT_SECRET`: Una cadena larga aleatoria para la seguridad de tokens.

## 💻 Instalación Local

### Con Docker (Recomendado)
```bash
docker build -t voice-dungeon .
docker run -p 8000:8000 -e GROQ_API_KEY=tu_key -e JWT_SECRET=secreto voice-dungeon
```

### Manual
1.  **Backend**:
    ```bash
    cd backend
    pip install -r requirements.txt
    python main.py
    ```
2.  **Frontend**:
    ```bash
    cd frontend
    # Compilar TS (opcional, ya se incluye estático)
    npm install && npm run build
    ```

## 📜 Licencia

Este proyecto se distribuye bajo la licencia MIT. ¡Siéntete libre de forkearlo y añadir tus propias mazmorras!
