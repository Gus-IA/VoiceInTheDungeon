import os
import json
import logging
from typing import Dict, Any, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("voice_in_the_dungeon.llm")

def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY no encontrada en variables de entorno (LLM)")
        return None
    # Limpiar comillas o espacios de .env
    api_key = api_key.strip().strip("'").strip('"')
    return Groq(api_key=api_key)

SYSTEM_PROMPT = """
Eres el motor narrativo y de interpretación de 'Voice in the Dungeon'.
Tu tarea es convertir la entrada del jugador en un JSON estructurado que contenga la intención, los parámetros y la respuesta narrativa en el idioma solicitado.

IDIOMA OBJETIVO: {language}

INTENTS soportados:
- move: El jugador quiere moverse (direcciones: north, south, east, west).
- look: El jugador quiere mirar a su alrededor.
- take: El jugador quiere coger un objeto (ej: flashlight).
- toggle_light: El jugador quiere encender/apagar la linterna.
- inventory: El jugador quiere ver qué lleva.
- open_door: El jugador quiere abrir una puerta.
- help: El jugador pide ayuda.
- unknown: Si no entiendes la intención.

INSTRUCCIONES DE RESPUESTA:
1. 'intent' y 'slots' deben seguir el esquema técnico (en inglés).
2. 'reply' DEBE ser una respuesta narrativa corta y misteriosa en el IDIOMA OBJETIVO ({language}).
3. 'ambient_whisper' (opcional) DEBE ser un susurro ambiental opcional en el IDIOMA OBJETIVO ({language}), solo si la situación lo amerita (pista, atmósfera, tensión).

Formato de respuesta (JSON estricto):
{{
  "intent": "intent_name",
  "slots": {{
    "direction": "north | south | east | west | null",
    "item": "flashlight | null",
    "action": "on | off | null"
  }},
  "reply": "Texto narrativo en {language}",
  "ambient_whisper": "Susurro opcional en {language} o null"
}}

IMPORTANTE: Responde ÚNICAMENTE con el bloque JSON. No traduzcas los nombres de los intents ni de los slots.
"""

def parse_command_llm(text: str, language: str = "es") -> Optional[Dict[str, Any]]:
    client = get_client()
    if not client:
        logger.warning("GROQ_API_KEY no configurada o inválida. Saltando LLM.")
        return None
    
    try:
        current_prompt = SYSTEM_PROMPT.format(language=language)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": current_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            timeout=5.0
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error llamando a Groq LLM: {e}")
        return None

def translate_reply(text: str, target_language: str) -> str:
    # Esta función queda deprecada ya que el nuevo parser traduce directamente.
    # Se mantiene por compatibilidad momentánea pero devuelve el texto original.
    return text
