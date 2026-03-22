import os
import json
import logging
import re
from typing import Optional, Dict, Any, List
from functools import lru_cache
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = {
    "es": {
        "mirar": "look", "ver": "look",
        "norte": "move", "sur": "move", "este": "move", "oeste": "move",
        "inventario": "inventory", "coger": "take", "linterna": "toggle_light",
        "encender": "toggle_light", "apagar": "toggle_light", "ayuda": "help", "abrir": "open_door",
    },
    "en": {
        "look": "look", "see": "look", "around": "look", "examine": "look", "room": "look",
        "north": "move", "south": "move", "east": "move", "west": "move", "go": "move", "walk": "move",
        "inventory": "inventory", "items": "inventory", "carrying": "inventory", "bag": "inventory",
        "take": "take", "grab": "take", "pick": "take", "get": "take", 
        "flashlight": "toggle_light", "light": "toggle_light", "lamp": "toggle_light",
        "on": "toggle_light", "off": "toggle_light", "turn": "toggle_light", "switch": "toggle_light",
        "help": "help", "options": "help", "commands": "help", "what": "help",
        "open": "open_door", "door": "open_door", "chest": "open_door", "unlock": "open_door",
        "hello": "en", "hi": "en", "hey": "en", "thanks": "en", "thank": "en"
    },
    "ja": {
        "見る": "look", "みる": "look",
        "北": "move", "南": "move", "東": "move", "西": "move",
        "持ち物": "inventory", "取る": "take", "ライト": "toggle_light",
        "つける": "toggle_light", "消す": "toggle_light", "ヘルプ": "help", "開ける": "open_door",
    },
    "fr": {
        "regarder": "look", "voir": "look", "autour": "look", "examine": "look",
        "nord": "move", "sud": "move", "est": "move", "ouest": "move", "aller": "move", "marcher": "move",
        "inventaire": "inventory", "objets": "inventory", "sac": "inventory",
        "prendre": "take", "saisir": "take", "ramasser": "take",
        "lampe": "toggle_light", "lumiere": "toggle_light", "torche": "toggle_light",
        "allume": "toggle_light", "eteint": "toggle_light", "ouvrir": "open_door", "porte": "open_door",
        "bonjour": "fr", "merci": "fr"
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

MESSAGES = {
    "es": {
        "pickup_flashlight": "Has recogido la linterna.",
        "already_have_flashlight": "Ya tienes la linterna.",
        "what_to_take": "¿Qué quieres coger?",
        "no_flashlight": "No tienes ninguna linterna.",
        "light_already_on": "La linterna ya está encendida.",
        "light_on": "Enciendes la linterna. La oscuridad retrocede a tu alrededor.",
        "light_off": "Apagas la linterna. La oscuridad vuelve a envolverte.",
        "light_already_off": "La linterna ya está apagada.",
        "inventory_prefix": "Llevas: ",
        "inventory_empty": "No llevas nada.",
        "no_path": "No parece haber ningún camino en esa dirección.",
        "reset_world": "La mazmorra se ha reestructurado por completo. Regresas al inicio en un nuevo mundo.",
        "victory": "¡Has encontrado la salida secreta! Eres libre... o puedes quedarte a explorar.",
        "too_dark": "Está demasiado oscuro para intentar abrir nada.",
        "nothing_to_open": "No ves nada que puedas abrir aquí.",
        "fallback": "No entiendo lo que intentas hacer. Di 'ayuda' para ver opciones."
    },
    "en": {
        "pickup_flashlight": "You have picked up the flashlight.",
        "already_have_flashlight": "You already have the flashlight.",
        "what_to_take": "What do you want to take?",
        "no_flashlight": "You don't have a flashlight.",
        "light_already_on": "The flashlight is already on.",
        "light_on": "You turn on the flashlight. The darkness recedes around you.",
        "light_off": "You turn off the flashlight. Darkness envelops you once more.",
        "light_already_off": "The flashlight is already off.",
        "inventory_prefix": "You are carrying: ",
        "inventory_empty": "You are carrying nothing.",
        "no_path": "There doesn't seem to be any path in that direction.",
        "reset_world": "The dungeon has been completely restructured. You return to the beginning in a new world.",
        "victory": "You've found the secret exit! You are free... or you can stay and explore.",
        "too_dark": "It's too dark to try to open anything.",
        "nothing_to_open": "You don't see anything you can open here.",
        "fallback": "I don't understand what you're trying to do. Say 'help' for options."
    }
}

def detect_language(text: str) -> str:
    """
    Detecta el idioma del texto basándose en palabras clave comunes.
    """
    text_lower = text.lower()
    # Palabras clave de alta confianza por idioma
    checks = {
        # Español primero para evitar falsos positivos en idiomas similares
        "es": ["mirar", "coger", "linterna", "inventario", "ayuda", "norte", "sur", "este", "oeste", "abrir", "puerta", "hola", "gracias"],
        "en": ["the", "is", "get", "take", "look", "inventory", "north", "south", "east", "west", "open", "door", "use", "flashlight", "hello", "around", "room", "examine"],
        "de": ["der", "die", "das", "ist", "norden", "suden", "osten", "westen", "inventar", "hilfe", "schauen", "sehen"],
        "fr": ["le", "la", "les", "nord", "sud", "est", "ouest", "inventaire", "regarder", "voir", "ouvrir"],
        "it": ["il", "la", "i", "gli", "le", "sud", "ovest", "guarda", "vedere"],
        "pt": ["os", "as", "leste", "olhar", "ver", "pegar"],
        "ja": ["見る", "行く", "北", "南", "東", "西", "アイテム", "助けて", "こんにちは"],
        "ru": ["смотреть", "идти", "север", "юг", "восток", "запад", "инвентарь", "привет"],
        "zh": ["看", "去", "北", "南", "东", "西", "物品", "帮助", "你好"],
        "nl": ["de", "het", "een", "noord", "zuid", "oost", "west", "kijk", "hallo"]
    }
    
    for lang, keywords in checks.items():
        if any(kw in text_lower for kw in keywords):
            # Para idiomas sin espacios (ja, zh), no usamos los espacios laterales
            if lang in ["ja", "zh"]:
                return lang
            # Para los demás, verificamos palabra completa si es corta
            if any(f" {kw} " in f" {text_lower} " for kw in keywords if len(kw) > 2):
                return lang
            elif any(kw == text_lower for kw in keywords):
                return lang
            
    return None # Regresar None si no hay nada claro


DIRECTIONS = {
    "norte": "north", "sur": "south", "este": "east", "oeste": "west",
    "north": "north", "south": "south", "east": "east", "west": "west",
    "nord": "north", "sud": "south", "est": "east", "ouest": "west",
    "norden": "north", "suden": "south", "osten": "east", "westen": "west",
    "leste": "east", "sul": "south", "北": "north", "南": "south", "東": "east", "西": "west"
}

DIRECTIONS_OPPOSITE = {
    "north": "south", "south": "north",
    "east": "west", "west": "east"
}

DUNGEON_THEMES = [
    "Cripta olvidada", "Laboratorio de alquimia en ruinas", "Túneles inundados", 
    "Prisión de almas", "Jardín subterráneo marchito", "Armería herrumbrada",
    "Cámara de tortura abandonada", "Mina de cristales oscuros", "Sagrario profanado"
]

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

PLAYER HISTORY (Concise summary of past key actions):
{history}

ROOM CONTEXT (Provided in Spanish, but YOU MUST TRANSLATE if player speaks another language):
{room_desc}

### LANGUAGE DETECTION & CONSISTENCY (CRITICAL):
- You are a UNIVERSAL language engine. 
- You MUST detect the player's language from their input and translate the ROOM CONTEXT accordingly.
- **NEVER reply in Spanish if the player speaks French, Japanese, German, etc.**
- **If the player's language differs from the TARGET LANGUAGE, priority goes to matching the player exactly.**
- The 'reply' and the 'language_code' MUST match the detected language perfectly.
- Ensure the tone is consistent across all languages.

### NARRATIVE FOCUS:
- Provide an atmospheric, descriptive response based on the ROOM CONTEXT.
- DO NOT include any special markers like [AMBIENT: ...] or SFX instructions.
- Keep the tone mysterious and immersive.

### INTENTS:
- move, look, take, toggle_light, inventory, open_door, help, unknown.

### JSON Response Format:
{{
  "intent": "intent_name",
  "slots": {{ "direction": "...", "item": "...", "action": "..." }},
  "reply": "Atmospheric text in the DETECTED language",
  "language_code": "ISO code"
}}
"""

LANG_MAP = {
    "es": "Español/Spanish",
    "en": "Inglés/English",
    "hi": "Hindi",
    "fr": "Francés/French",
    "de": "Alemán/German",
    "it": "Italiano/Italian",
    "pt": "Portugués/Portuguese",
    "ja": "Japonés/Japanese",
    "zh": "Chino/Chinese",
    "ru": "Ruso/Russian",
    "nl": "Holandés/Dutch",
    "auto": "Automatic Detection (Detect and match the player's language)"
}

LANGUAGE_ALIASES = {
    "spanish": "es", "esp": "es", "es-es": "es",
    "english": "en", "eng": "en", "en-us": "en", "en-gb": "en",
    "french": "fr", "fra": "fr", "fr-fr": "fr",
    "german": "de", "deu": "de", "ger": "de", "de-de": "de",
    "japanese": "ja", "jpn": "ja", "jp": "ja", "ja-jp": "ja",
    "chinese": "zh", "zho": "zh", "chi": "zh", "zh-cn": "zh", "zh-tw": "zh",
    "russian": "ru", "rus": "ru", "ru-ru": "ru",
    "italian": "it", "ita": "it", "it-it": "it",
    "portuguese": "pt", "por": "pt", "pt-pt": "pt", "pt-br": "pt",
    "dutch": "nl", "nld": "nl", "dut": "nl", "nl-nl": "nl"
}

SYSTEM_PROMPT_ROOM_GEN = """
Eres el Maestro de Mazmorras de un juego de aventuras procedural.
El jugador se está moviendo hacia el {direction} desde esta habitación:
"{current_room_desc}"

Genera una nueva habitación atmosférica que conecte con la anterior.
Mantén el tono oscuro, misterioso y ligeramente claustrofóbico de 'Voice in the Dungeon'.

FORMATO DE RESPUESTA (SOLO JSON):
{{
  "name": "Nombre de la Sala",
  "description": "Descripción atmosférica (2-3 frases)",
  "exits": {{ "{back_direction}": "PREVIOUS_ROOM_ID", "random_exit_1": "EMPTY", ... }}
}}

TEMA DE LA SALA: {theme}

IMPORTANTE:
1. El campo 'exits' DEBE incluir una salida que vuelva a la habitación anterior ({back_direction}).
2. Otras salidas deben marcarse como "EMPTY" para que el sistema las genere después.
3. No incluyas explicaciones, SOLO el objeto JSON.
4. IDIOMA DE SALIDA: {language}
5. Usa el TEMA DE LA SALA indicado para inspirar el nombre y la descripción.
"""

def generate_procedural_room(current_room_desc: str, direction: str, language: str = "es") -> Optional[Dict[str, Any]]:
    """
    Usa el LLM para generar una nueva habitación basada en la dirección y el contexto.
    """
    client = get_client()
    if not client:
        return None

    # Mapeo de direcciones opuestas para la salida de vuelta
    opposite = {
        "north": "south", "south": "north",
        "east": "west", "west": "east"
    }
    back_direction = opposite.get(direction, "inicio")
    
    full_lang = LANG_MAP.get(language, language)
    
    import random
    theme = random.choice(DUNGEON_THEMES)
    
    try:
        prompt = SYSTEM_PROMPT_ROOM_GEN.format(
            direction=direction,
            current_room_desc=current_room_desc,
            back_direction=back_direction,
            language=full_lang,
            theme=theme
        )
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            timeout=7.0
        )
        
        content = completion.choices[0].message.content
        res = json.loads(content)
        
        # Validar estructura básica
        if "name" not in res or "description" not in res:
            return None
            
        return res
    except Exception as e:
        logger.error(f"Error generando habitación procedimental: {e}")
        return None
def parse_command_llm(text: str, language: str = "es", room_desc: str = "", history: str = "") -> Optional[Dict[str, Any]]:
    client = get_client()
    if not client:
        logger.warning("GROQ_API_KEY no configurada o inválida. Saltando LLM.")
        return None
    
    try:
        full_lang = LANG_MAP.get(language, language)
        # Escapamos las llaves en los datos dinámicos para evitar errores de .format()
        safe_room_desc = room_desc.replace("{", "{{").replace("}", "}}")
        safe_history = history.replace("{", "{{").replace("}", "}}")
        current_prompt = SYSTEM_PROMPT.format(language=full_lang, room_desc=safe_room_desc, history=safe_history)
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

@lru_cache(maxsize=128)
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
def local_generate_room(direction: str, current_room_desc: str = "", language: str = "es") -> Dict[str, Any]:
    """
    Generador de habitaciones basado en plantillas para cuando el LLM falla.
    """
    import random
    
    themes = [
        {"name": "Pasillo de Antorchas", "desc": "Un pasillo largo iluminado por antorchas que chisporrotean en las paredes de piedra húmeda."},
        {"name": "Cámara de Almacenamiento", "desc": "Una habitación pequeña llena de cajas rotas y estantes carcomidos por el tiempo."},
        {"name": "Cripta Pequeña", "desc": "Un lugar silencioso con hornacinas excavadas en la pared. El olor a polvo es sofocante."},
        {"name": "Intersección de Túneles", "desc": "Varios caminos se cruzan aquí. El techo es bajo y gotea un agua de color oscuro."},
        {"name": "Sala de Guardia Abandonada", "desc": "Hay una mesa volcada y una silla rota. Restos de una antigua vigilancia que ya no existe."},
        {"name": "Gruta Natural", "desc": "Las paredes de piedra han dejado paso a formaciones naturales. Se oye un murmullo de agua lejana."},
        {"name": "Vestíbulo en Ruinas", "desc": "Grandes pilares de mármol sostienen a duras penas un techo que amenaza con desplomarse."},
        {"name": "Laboratorio de Alquimia", "desc": "Frascos de vidrio rotos cubren el suelo. Hay un extraño residuo fluorescente en un mortero."},
        {"name": "Dormitorios Comunes", "desc": "Varios catres podridos se alinean contra las paredes. Un silencio sepulcral lo domina todo."}
    ]
    
    selected = random.choice(themes)
    res = {
        "name": selected["name"],
        "description": selected["desc"],
        "description_dark": "La oscuridad es casi total. Apenas distingues las formas de lo que parece ser " + selected["name"].lower() + ".",
        "exits": {}, # Se rellenará en main.py
        "objects": []
    }
    
    # Traducir si es necesario
    if language != "es":
        res["name"] = translate_reply(res["name"], language)
        res["description"] = translate_reply(res["description"], language)
        
    return res
