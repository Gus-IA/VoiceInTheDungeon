import os
import logging
from typing import Optional, Dict
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("voice_in_the_dungeon.transcription")

def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY no encontrada en variables de entorno")
        return None
    # Limpiar posibles comillas o espacios de .env mal formateados
    api_key = api_key.strip().strip("'").strip('"')
    return Groq(api_key=api_key)

def transcribe_audio(file_path: str) -> Optional[Dict[str, str]]:
    client = get_client()
    if not client:
        logger.warning("GROQ_API_KEY no configurada. Saltando transcripción.")
        return None
    
    try:
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(file_path), file.read()),
                model="whisper-large-v3-turbo",
                response_format="json"
            )
            # Whisper large v3 turbo detecta el idioma, pero en el formato 'json' normal 
            # de Groq a veces solo devuelve 'text'. Si queremos idioma, a veces hay que usar verbose_json.
            return {
                "text": transcription.text,
                "language": getattr(transcription, "language", "unknown")
            }
    except Exception as e:
        logger.error(f"Error transcribiendo audio: {e}")
        return None
