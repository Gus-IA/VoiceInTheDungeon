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
Eres el intérprete de comandos de un juego de mazmorras (Voice in the Dungeon).
Tu tarea es convertir el texto en lenguaje natural del jugador a un JSON estructurado.

INTENTS soportados:
- move: El jugador quiere moverse a una dirección (north, south, east, west).
- look: El jugador quiere mirar a su alrededor.
- take: El jugador quiere coger un objeto (ej: flashlight).
- toggle_light: El jugador quiere encender o apagar la linterna.
- inventory: El jugador quiere ver qué lleva.
- open_door: El jugador quiere abrir una puerta o cruzarla.
- help: El jugador pide ayuda o no sabe qué hacer.
- unknown: Si no entiendes la intención.

Formato de respuesta (JSON estricto):
{
  "intent": "intent_name",
  "slots": {
    "direction": "north | south | east | west | null",
    "item": "flashlight | null",
    "action": "on | off | null"
  }
}

IMPORTANTE: Responde ÚNICAMENTE con el bloque JSON.
"""

def parse_command_llm(text: str) -> Optional[Dict[str, Any]]:
    client = get_client()
    if not client:
        logger.warning("GROQ_API_KEY no configurada o inválida. Saltando LLM.")
        return None
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0,
            response_format={"type": "json_object"},
            timeout=3.0
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error llamando a Groq LLM: {e}")
        return None

def translate_reply(text: str, target_language: str) -> str:
    client = get_client()
    if not client or not target_language or target_language.startswith("es"):
        return text
    
    try:
        prompt = f"Traduce la siguiente frase del juego al idioma '{target_language}'. Mantén el tono misterioso y narrativo. Responde solo con la traducción:\n\n{text}"
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            timeout=3.0
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error traduciendo respuesta: {e}")
        return text
