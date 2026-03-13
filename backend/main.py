import sys
from pathlib import Path
import json
import logging
import os
from time import time
from uuid import uuid4
from datetime import datetime
import hashlib
import sqlite3
from typing import Optional

# Asegurar que el directorio 'backend' esté en el path para los imports
sys.path.append(str(Path(__file__).parent))

from fastapi import FastAPI, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from dotenv import load_dotenv

import auth
import transcription
import llm_parser
from typing import Any

load_dotenv()

logger = logging.getLogger("voice_in_the_dungeon")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas de proyecto y datos
PROJECT_ROOT = Path(__file__).parent.parent
STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "saves.db"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CLIENT_HASH_SALT = "voice_in_the_dungeon_salt_v1"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")


def get_db_connection():
    """
    Obtiene una conexión a la base de datos. 
    Soporta PostgreSQL si DATABASE_URL está definida (para Render/Heroku),
    de lo contrario usa SQLite local.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url)
    else:
        return sqlite3.connect(DB_PATH)


def _init_db() -> None:
    conn = get_db_connection()
    try:
        # Tabla de usuarios
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        # Tabla de partidas vinculada a usuario
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saves (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
    finally:
        conn.close()


_init_db()


async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = auth.decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
            )
        return {"id": user[0], "username": user[1]}
    finally:
        conn.close()


class CommandRequest(BaseModel):
    text: str
    state: dict | None = None
    language: str = "es"


class CommandResponse(BaseModel):
    reply: str
    state: dict
    detected_language: str = "es"


class SaveGameIn(BaseModel):
    state: dict


class SaveGameOut(BaseModel):
    save_id: str


class LoadGameOut(BaseModel):
    state: dict


class UserCreate(BaseModel):
    username: str
    password: str


@app.post("/api/register")
def register(user: UserCreate):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (user.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
        
        user_id = str(uuid4())
        hashed_pw = auth.get_password_hash(user.password)
        now = datetime.utcnow().isoformat() + "Z"
        
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, user.username, hashed_pw, now),
        )
        conn.commit()
        return {"message": "Usuario registrado con éxito"}
    finally:
        conn.close()


@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (form_data.username,)
        )
        user = cur.fetchone()
        if not user or not auth.verify_password(form_data.password, user[2]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = auth.create_access_token(data={"sub": user[1]})
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        conn.close()


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    file_path = UPLOAD_DIR / f"{uuid4()}.webm"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    result = transcription.transcribe_audio(str(file_path))
    
    # Cleanup file
    if file_path.exists():
        file_path.unlink()
        
    if not result:
        raise HTTPException(status_code=500, detail="Error en la transcripción")
        
    return result


_init_db()


def _anonymized_client_hash(request: Request) -> str:
    """
    Devuelve un hash estable (pero anónimo) del cliente a partir de la IP y User-Agent.
    Pensado para analizar uso sin almacenar datos personales directos.
    """
    # Render y otros proxies suelen enviar X-Forwarded-For
    xff = request.headers.get("x-forwarded-for") or ""
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else ""

    user_agent = request.headers.get("user-agent", "")

    base = f"{CLIENT_HASH_SALT}|{ip}|{user_agent}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    # Suficiente para agrupar sesiones sin ser excesivamente identificable
    return digest[:16]

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


ROOMS = {
    "inicio": {
        "name": "Habitación oscura",
        "description": "Estás en una habitación pequeña y oscura. Hay una puerta al norte.",
        "description_dark": "Todo está demasiado oscuro para ver algo. Solo intuyes una puerta al norte.",
        "exits": {"norte": "pasillo"},
    },
    "pasillo": {
        "name": "Pasillo de piedra",
        "description": "Te encuentras en un pasillo húmedo de piedra que se prolonga al este y al oeste.",
        "description_dark": "Notas un largo pasillo, pero apenas ves nada sin luz.",
        "exits": {"sur": "inicio", "este": "sala_guardia"},
    },
    "sala_guardia": {
        "name": "Sala de guardia",
        "description": "Una vieja sala de guardia con mesas volcadas y un arcón cerrado.",
        "description_dark": "Tropiezas con muebles en la oscuridad; parece una habitación amplia.",
        "exits": {"oeste": "pasillo"},
    },
}


def describe_room(state: dict) -> str:
    room_id = str(state.get("room", "inicio"))
    room = ROOMS.get(room_id, ROOMS["inicio"])
    flashlight_on = bool(state.get("flashlight_on", False))

    base = str(room["description"]) if flashlight_on else str(room["description_dark"])

    extra = ""
    inventory = state.get("inventory", [])
    if not isinstance(inventory, list):
        inventory = []

    if room_id == "inicio" and "flashlight" not in inventory:
        extra = " En el suelo distingues la silueta de una linterna."
    if room_id == "sala_guardia" and flashlight_on:
        if state.get("game_won"):
            extra += " El arcón está abierto. Has encontrado el tesoro y la salida."
        else:
            extra += " Ves un arcón de madera con un candado oxidado."

    return base + extra


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time()
    request_id = str(uuid4())
    client_hash = _anonymized_client_hash(request)

    # Guardamos contexto en el request para reutilizarlo en otros logs
    request.state.request_id = request_id
    request.state.client_hash = client_hash

    response = await call_next(request)
    duration_ms = (time() - start) * 1000

    log_record = {
        "event": "http_request",
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round(float(duration_ms), 2),
        "request_id": request_id,
        "client_hash": client_hash,
        "user_agent": request.headers.get("user-agent", ""),
    }
    logger.info(json.dumps(log_record, ensure_ascii=False))
    return response


@app.post("/api/command", response_model=CommandResponse)
def process_command(body: CommandRequest, request: Request, user: dict = Depends(get_current_user)):
    text = body.text.strip()
    raw_state = body.state or {"room": "inicio", "inventory": []}
    state: dict[str, Any] = dict(raw_state)
    state["flashlight_on"] = bool(state.get("flashlight_on", False))
    state["inventory"] = list(state.get("inventory", [])) # type: ignore
    state["game_won"] = bool(state.get("game_won", False)) # type: ignore
    target_lang = body.language

    logger.info(
        json.dumps(
            {
                "event": "command_received",
                "text": text,
                "user_id": user["id"],
                "language": target_lang,
                "room": state.get("room", "inicio"),
            },
            ensure_ascii=False,
        )
    )

    # 1. Intentar parsear con LLM unificado (Incluye traducción y ambiente si el LLM lo genera)
    # Si el idioma no es español, forzamos a que el LLM traduzca la descripción
    # pasando la descripción base como prompt si el intent es 'mirar'
    room_desc = describe_room(state)
    llm_result = llm_parser.parse_command_llm(text, target_lang, room_desc)
    
    # 1.1 Fallback local si el LLM falla o no está configurado
    if not llm_result:
        logger.info("Usando fallback local para el comando.")
        llm_result = llm_parser.local_parse_command(text, target_lang)
        
    intent = llm_result.get("intent") if llm_result else None
    slots = llm_result.get("slots", {}) if llm_result else {}
    llm_reply = llm_result.get("reply") if llm_result else None
    ambient_whisper = llm_result.get("ambient_whisper") if llm_result else None

    # --- NUEVA SECCIÓN: Resolución de Idioma antes de la Lógica ---
    detected_lang = llm_result.get("language_code") if llm_result else None
    
    # Normalización: 'eng' -> 'en', 'french' -> 'fr', etc.
    if detected_lang:
        detected_lang = str(detected_lang).lower().strip()
        if len(detected_lang) > 2:
            for code, name in llm_parser.LANG_MAP.items():
                if name.lower() in detected_lang:
                    detected_lang = code
                    break
            detected_lang = detected_lang[:2]

    # Fallback final si no hay detección
    if not detected_lang or detected_lang in ["au", "no"]: 
        detected_lang = target_lang if target_lang != "auto" else "es"
    
    if len(detected_lang) != 2:
        detected_lang = "es"
    # --- FIN Resolución Idioma ---

    reply = None

    # 2. Lógica de juego basada en Intent
    if intent == "help" or any(kw in text.lower() for kw in ["ayuda", "help", "aide", "hilfe", "aiuto", "ajuda", "ヘルプ"]):
        reply = llm_parser.HELP_MESSAGES.get(detected_lang, llm_parser.HELP_MESSAGES["es"])

    elif intent == "look" or "mirar" in text.lower():
        reply = describe_room(state)

    elif intent == "take" or "coger" in text.lower():
        # Asegurar que slots no sea None y que el valor no sea None
        item = (slots.get("item") or "").lower() if slots else ""
        if "linterna" in text.lower() or item == "flashlight":
            inventory = state.get("inventory")
            if not isinstance(inventory, list):
                inventory = []
            if "flashlight" not in inventory:
                inventory.append("flashlight")
                state["inventory"] = inventory
                reply = "Coges la linterna. Te sientes un poco más seguro."
            else:
                reply = "Ya tienes la linterna."
        else:
            reply = "¿Qué quieres coger?"

    elif intent == "toggle_light" or "linterna" in text.lower():
        # Asegurar que slots no sea None y que el valor no sea None
        action = (slots.get("action") or "").lower() if slots else ""
        has_flashlight = "flashlight" in state.get("inventory", [])
        
        if not has_flashlight:
            reply = "No tienes ninguna linterna."
        else:
            # Detectar si quiere encender o apagar si el LLM no fue claro
            is_on = "encender" in text.lower() or "prender" in text.lower() or action == "on"
            is_off = "apagar" in text.lower() or action == "off"
            
            if is_on:
                if state.get("flashlight_on"):
                    reply = "La linterna ya está encendida."
                else:
                    state["flashlight_on"] = True
                    reply = "Enciendes la linterna. La oscuridad retrocede a tu alrededor."
            elif is_off:
                if state.get("flashlight_on"):
                    state["flashlight_on"] = False
                    reply = "Apagas la linterna. La oscuridad vuelve a envolverte."
                else:
                    reply = "La linterna ya está apagada."
            else:
                # Toggle
                state["flashlight_on"] = not state.get("flashlight_on")
                reply = "Encendida" if state["flashlight_on"] else "Apagada"

    elif intent == "inventory" or "inventario" in text.lower() or "inventaire" in text.lower() or "inventar" in text.lower():
        inventory = state.get("inventory", [])
        if inventory:
            # Localizar nombres de objetos si es posible
            items_localized = []
            for item in inventory:
                if item == "flashlight":
                    items_localized.append("flashlight" if detected_lang == "en" else "linterna")
                else:
                    items_localized.append(item)
            
            if detected_lang == "es":
                reply = "Llevas: " + ", ".join(items_localized)
            elif detected_lang == "de":
                reply = "Du trägst: " + ", ".join(items_localized)
            elif detected_lang == "fr":
                reply = "Tu portes : " + ", ".join(items_localized)
            else:
                reply = "You are carrying: " + ", ".join(items_localized)
        else:
            if detected_lang == "es":
                reply = "No llevas nada."
            else:
                reply = "You are carrying nothing."

    elif intent == "move" or any(d in text.lower() for d in ["norte", "sur", "este", "oeste", "north", "south", "east", "west"]):
        current_room_id = state.get("room", "inicio")
        current_room = ROOMS.get(current_room_id, ROOMS["inicio"])

        direction = slots.get("direction") if slots else None
        if direction:
            direction = str(direction).lower()
        
        # Mapeo universal para la lógica interna
        direction = llm_parser.DIRECTIONS.get(direction or "", direction)
        
        # Fallback manual si el LLM falla o no detectó dirección
        if not direction:
            for kw_dir, eng_dir in llm_parser.DIRECTIONS.items():
                if kw_dir in text.lower():
                    direction = eng_dir
                    break

        if direction and direction in current_room["exits"]:
            new_room_id = current_room["exits"][direction]
            state["room"] = new_room_id
            reply = describe_room(state)
        else:
            reply = "No parece haber ningún camino en esa dirección."

    elif intent == "open_door" or "abrir puerta" in text.lower() or "abrir arcon" in text.lower() or "abrir arcón" in text.lower():
        current_room_id = state.get("room", "inicio")
        if current_room_id == "inicio":
            state["room"] = "pasillo"
            reply = (
                "Abres la puerta con esfuerzo. Cruzas al pasillo.\n" + describe_room(state)
            )
        elif current_room_id == "sala_guardia":
            if state.get("flashlight_on"):
                state["game_won"] = True
                reply = (
                    "Forcejeas con el candado oxidado hasta que cede. El arcón se abre revelando "
                    "un mapa y un túnel secreto que conduce al exterior. ¡Has escapado del calabozo!"
                )
            else:
                reply = "Está demasiado oscuro para intentar abrir nada. Podrías hacerte daño."
        else:
            reply = "No ves nada que puedas abrir aquí."

    # 4. Respuesta final: Priorizamos 'reply' (lógica de juego) si existe.
    if reply:
        # Si ya es un HELP_MESSAGE o INVENTORY, no hace falta re-traducir (evita alucinaciones)
        already_localized = reply in llm_parser.HELP_MESSAGES.values() or reply.startswith("Llevas:") or reply.startswith("You are carrying:") or reply.startswith("Du trägst:")
        
        if already_localized:
            final_reply = reply
        else:
            final_reply = llm_parser.translate_reply(reply, detected_lang)
    elif llm_reply and intent != "unknown":
        final_reply = llm_reply
    else:
        # Si nada funcionó, fallback genérito
        fallback = "No entiendo lo que intentas hacer. Di 'ayuda' para ver opciones."
        final_reply = llm_parser.translate_reply(fallback, detected_lang)

    # Limpiar reply
    final_reply = str(final_reply).strip()

    logger.info(
        json.dumps(
            {
                "event": "command_result",
                "text": text,
                "user_id": user["id"],
                "reply": final_reply,
                "detected_language": detected_lang,
                "room": state.get("room"),
            },
            ensure_ascii=False,
        )
    )

    return CommandResponse(reply=str(final_reply), state=state, detected_language=str(detected_lang)) # type: ignore



@app.post("/api/save", response_model=SaveGameOut)
def save_game(body: SaveGameIn, request: Request, user: dict = Depends(get_current_user)) -> SaveGameOut:
    """
    Guarda una partida vinculada al usuario.
    """
    save_id = str(uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO saves (id, user_id, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (save_id, user["id"], json.dumps(body.state, ensure_ascii=False), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info(
        json.dumps(
            {
                "event": "game_saved",
                "save_id": save_id,
                "user_id": user["id"],
                "request_id": getattr(request.state, "request_id", None),
                "client_hash": getattr(request.state, "client_hash", None),
            },
            ensure_ascii=False,
        )
    )

    return SaveGameOut(save_id=str(save_id)) # type: ignore


@app.get("/api/save/{save_id}", response_model=LoadGameOut)
def load_game(save_id: str, request: Request, user: dict = Depends(get_current_user)) -> LoadGameOut:
    """
    Recupera una partida si pertenece al usuario.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT state_json, user_id FROM saves WHERE id = ?", (save_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    
    if row[1] != user["id"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta partida")

    state = json.loads(row[0])

    logger.info(
        json.dumps(
            {
                "event": "game_loaded",
                "save_id": save_id,
                "user_id": user["id"],
                "room": state.get("room", "inicio"),
                "request_id": getattr(request.state, "request_id", None),
                "client_hash": getattr(request.state, "client_hash", None),
            },
            ensure_ascii=False,
        )
    )

    return LoadGameOut(state=dict(state)) # type: ignore

