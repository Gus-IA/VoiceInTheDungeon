from typing import Dict, Any, Optional
import os
import json
import logging

KEYWORDS = {
    "es": {
        "mirar": "look", "ver": "look",
        "norte": "move", "sur": "move", "este": "move", "oeste": "move",
        "inventario": "inventory", "coger": "take", "linterna": "toggle_light",
        "encender": "toggle_light", "apagar": "toggle_light", "ayuda": "help", "abrir": "open_door",
    },
    "en": {
        "look": "look",
        "north": "move", "south": "move", "east": "move", "west": "move",
        "inventory": "inventory", "take": "take", "flashlight": "toggle_light",
        "on": "toggle_light", "off": "toggle_light", "help": "help", "open": "open_door",
    },
    "ja": {
        "見る": "look", "みる": "look",
        "北": "move", "南": "move", "東": "move", "西": "move",
        "持ち物": "inventory", "取る": "take", "ライト": "toggle_light",
        "つける": "toggle_light", "消す": "toggle_light", "ヘルプ": "help", "開ける": "open_door",
    },
    "fr": {
        "regarder": "look", "voir": "look",
        "nord": "move", "sud": "move", "est": "move", "ouest": "move",
        "inventaire": "inventory", "prendre": "take", "lampe": "toggle_light",
        "allumer": "toggle_light", "eteindre": "toggle_light", "aide": "help", "ouvrir": "open_door",
    },
    "de": {
        "schauen": "look", "sehen": "look",
        "norden": "move", "suden": "move", "osten": "move", "westen": "move",
        "inventar": "inventory", "nehmen": "take", "taschenlampe": "toggle_light",
        "an": "toggle_light", "aus": "toggle_light", "hilfe": "help", "offnen": "open_door",
    },
    "it": {
        "guarda": "look", "vedere": "look",
        "nord": "move", "sud": "move", "est": "move", "ovest": "move",
        "inventario": "inventory", "prendere": "take", "torcia": "toggle_light",
        "accendere": "toggle_light", "spegnere": "toggle_light", "aiuto": "help", "aprire": "open_door",
    },
    "pt": {
        "olhar": "look", "ver": "look",
        "norte": "move", "sul": "move", "leste": "move", "oeste": "move",
        "inventario": "inventory", "pegar": "take", "lanterna": "toggle_light",
        "ligar": "toggle_light", "desligar": "toggle_light", "ajuda": "help", "abrir": "open_door",
    }
}

HELP_MESSAGES = {
    "es": "Puedes decir cosas como: 'mirar', 'coger linterna', 'inventario', 'encender linterna', 'apagar linterna', 'ir norte/sur/este/oeste' o 'abrir puerta'.",
    "en": "You can say things like: 'look', 'take flashlight', 'inventory', 'turn on flashlight', 'turn off flashlight', 'go north/south/east/west' or 'open door'.",
    "fr": "Vous pouvez dire des choses comme: 'regarder', 'prendre la lampe', 'inventaire', 'allumer la lampe', 'éteindre la lampe', 'aller au nord/sud/est/ouest' ou 'ouvrir la porte'.",
    "de": "Du kannst Dinge sagen wie: 'schauen', 'Taschenlampe nehmen', 'Inventar', 'Taschenlampe einschalten', 'Taschenlampe ausschalten', 'gehe Norden/Süden/Osten/Westen' oder 'Tür öffnen'.",
    "it": "Puoi dire cose come: 'guarda', 'prendi torcia', 'inventario', 'accendi torcia', 'spegni torcia', 'vai a nord/sud/est/ovest' o 'apri porta'.",
    "pt": "Você pode dizer coisas como: 'olhar', 'pegar lanterna', 'inventário', 'ligar lanterna', 'desligar lanterna', 'ir para norte/sul/leste/oeste' o 'abrir porta'.",
    "ja": "次のようなことができます： '見る', 'ライトを取る', '持ち物', 'ライトをつける', 'ライトを消す', '北/南/東/西に行く', 'ドアを開ける'。"
}

DIRECTIONS = {
    "norte": "north", "sur": "south", "este": "east", "oeste": "west",
    "north": "north", "south": "south", "east": "east", "west": "west",
    "nord": "north", "sud": "south", "est": "east", "ouest": "west",
    "norden": "north", "suden": "south", "osten": "east", "westen": "west",
    "leste": "east", "sul": "south", "北": "north", "南": "south", "東": "east", "西": "west"
}
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
You are the narrative engine for 'Voice in the Dungeon'.
Your task is to parse player input into JSON and provide an atmospheric response.

TARGET LANGUAGE: {language}

ROOM CONTEXT (Provided in Spanish, but YOU MUST TRANSLATE if player speaks another language):
{room_desc}

### LANGUAGE DETECTION & CONSISTENCY (CRITICAL):
- You are a UNIVERSAL language engine. 
- You MUST detect the player's language from their input and translate the ROOM CONTEXT accordingly.
- **NEVER reply in Spanish if the player speaks French, Japanese, German, etc.**
- The 'reply' and the 'language_code' MUST match the detected language perfectly.
- Ensure the tone is consistent across all languages.

### NARRATIVE FOCUS:
- Provide an atmospheric, descriptive response based on the ROOM CONTEXT.
- DO NOT include any special markers like [AMBIENT: ...] or SFX instructions.
- Keep the tone mysterious and immersive.

### INTENTS:
- move, look, take, toggle_light, inventory, open_door, help, unknown.

### JSON Response Format:
{
  "intent": "intent_name",
  "slots": { "direction": "...", "item": "...", "action": "..." },
  "reply": "Atmospheric text in the DETECTED language",
  "language_code": "ISO code"
}
"""

LANG_MAP = {
    "es": "Español/Spanish",
    "en": "Inglés/English",
    "hi": "Hindi",
    "fr": "Francés/French",
    "de": "Alemán/German",
    "it": "Italiano/Italian",
    "pt": "Portugués/Portuguese",
    "auto": "Automatic Detection (Detect and match the player's language)"
}

def parse_command_llm(text: str, language: str = "es", room_desc: str = "") -> Optional[Dict[str, Any]]:
    client = get_client()
    if not client:
        logger.warning("GROQ_API_KEY no configurada o inválida. Saltando LLM.")
        return None
    
    try:
        full_lang = LANG_MAP.get(language, language)
        current_prompt = SYSTEM_PROMPT.format(language=full_lang, room_desc=room_desc)
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
        # Extraer JSON de forma robusta por si Groq devuelve basura
        content = completion.choices[0].message.content
        try:
            res = json.loads(content)
        except json.JSONDecodeError:
            # Buscar el primer '{' y el último '}'
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                res = json.loads(match.group())
            else:
                raise

        # Asegurar que siempre haya un language_code, fallback al solicitado si no hay
        if "language_code" not in res:
            res["language_code"] = language if language != "auto" else "es"
        return res
    except Exception as e:
        logger.error(f"Error llamando a Groq LLM: {e}")
        return None

def translate_reply(text: str, target_language: str) -> str:
    """
    Traduce un bloque de texto al idioma objetivo usando el LLM.
    Ideal para descripciones de salas o mensajes de sistema que no están localizados.
    """
    if not text or not target_language or target_language == "es":
        return text

    client = get_client()
    if not client:
        return text

    # Mapeo de auto a algo usable si llega a este punto (aunque main.py debería resolverlo)
    lang_name = LANG_MAP.get(target_language, target_language)

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"Eres un traductor experto. Traduce el siguiente texto de juego de rol al {lang_name}. Mantén el tono misterioso. Responde SOLO con la traducción."},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            timeout=3.0
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error en translate_reply: {e}")
        return text

def local_parse_command(text: str, language: str = "es") -> Optional[Dict[str, Any]]:
    """
    Intento de parseo local basado en palabras clave (keyword fallback).
    Maneja intents básicos sin depender del LLM.
    """
    text_lower = text.lower()
    found_intent = None
    detected_lang_code = None
    
    # 1. Búsqueda por palabra EXACTA (Máxima prioridad para evitar colisiones)
    # Ejemplo: 'inventario' no debe matchear 'inventar' de alemán
    # Limpiamos puntuación básica para la comparación exacta
    text_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in text_lower)
    words = text_clean.split()
    
    # Prioridad: ES y EN primero si están presentes
    priority_langs = ["es", "en", "ja", "de", "fr", "it", "pt"]
    for lang_code in priority_langs:
        keywords = KEYWORDS.get(lang_code, {})
        for kw, intent in keywords.items():
            if kw in words:
                found_intent = intent
                detected_lang_code = lang_code
                break
        if found_intent:
            break
            
    # 2. Búsqueda por SUBCADENA (Fallback para idiomas sin espacios como Japonés o frases)
    if not found_intent:
        # Priorizamos keywords más largas para evitar falsos positivos
        # Recopilamos todas y ordenamos
        all_kws = []
        for l_code, kws in KEYWORDS.items():
            for kw, intent in kws.items():
                all_kws.append((kw, intent, l_code))
        
        # Ordenar por longitud descendente para que 'norden' gane a 'nord'
        all_kws.sort(key=lambda x: len(x[0]), reverse=True)
        
        for kw, intent, l_code in all_kws:
            if kw in text_lower:
                # Caso especial: si es latino/germánico, pedir que no sea parte de otra palabra
                # usando una regex simple o espacio aproximado.
                # Para Japonés (l_code == 'ja') permitimos substring puro.
                if l_code == 'ja' or f" {kw} " in f" {text_lower} ":
                    found_intent = intent
                    detected_lang_code = l_code
                    break
                # Fallback de seguridad si no hay espacios (ej: 'mirarnorte')
                elif len(kw) > 4 and kw in text_lower:
                    found_intent = intent
                    detected_lang_code = l_code
                    break
            
    if not found_intent:
        return None
        
    slots: Dict[str, Optional[str]] = {"direction": None, "item": None, "action": None}
    
    # Extraer dirección
    for kw_dir, eng_dir in DIRECTIONS.items():
        if kw_dir in text_lower:
            slots["direction"] = eng_dir
            break
            
    # Extraer item (linterna)
    if "linterna" in text_lower or "flashlight" in text_lower:
        slots["item"] = "flashlight"
        
    # Extraer acción
    if any(x in text_lower for x in ["encender", "prender", "on", "activar"]):
        slots["action"] = "on"
    elif any(x in text_lower for x in ["apagar", "off", "desactivar"]):
        slots["action"] = "off"
        
    # Usar el idioma detectado en el primer paso si estaba en 'auto'
    if language == "auto":
        local_lang = detected_lang_code or "es"
    else:
        local_lang = language

    return {
        "intent": found_intent,
        "slots": slots,
        "reply": None,
        "language_code": local_lang
    }
