import sys
from pathlib import Path
import json
import logging
import os
from time import time
from uuid import uuid4
from datetime import datetime, timezone
import hashlib
import sqlite3
from typing import Any, cast

# Asegurar que el directorio 'backend' esté en el path para los imports
import traceback
sys.path.append(str(Path(__file__).parent))

from fastapi import FastAPI, Request, HTTPException, Depends, status, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
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
app = FastAPI(title="Voice in the Dungeon API")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = traceback.format_exc()
    logger.error(f"Global error: {error_msg}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": error_msg if os.getenv("DEBUG") else None}
    )

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
    Soporta PostgreSQL si DATABASE_URL está definida, si no SQLite.
    """
    try:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            import psycopg2
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            # Asegurar sslmode para Neon
            if "?" not in db_url:
                db_url += "?sslmode=require"
            elif "sslmode" not in db_url:
                db_url += "&sslmode=require"
            return psycopg2.connect(db_url)
        else:
            return sqlite3.connect(DB_PATH)
    except Exception as e:
        logger.error(f"CRITICAL: Error conectando a la DB: {e}")
        raise e

def db_query(conn, sql: str, params: tuple = ()):
    """
    Helper para ejecutar queries independientemente de si es SQLite (?) o Postgres (%s).
    """
    is_postgres = not isinstance(conn, sqlite3.Connection)
    if is_postgres:
        sql = sql.replace("?", "%s")
    
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def _init_db() -> None:
    conn = get_db_connection()
    try:
        # Tabla de usuarios
        db_query(conn,
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
        db_query(conn,
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
        # Tabla de habitaciones procedimentales (para evitar pérdida en FS efímero)
        db_query(conn,
            """
            CREATE TABLE IF NOT EXISTS dungeon_rooms (
                id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL
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
        cur = db_query(conn, "SELECT id, username FROM users WHERE username = ?", (username,))
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
    language: str = "auto"


class CommandResponse(BaseModel):
    reply: str
    state: dict[str, Any]
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
        cur = db_query(conn, "SELECT id FROM users WHERE username = ?", (user.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
        
        user_id = str(uuid4())
        hashed_pw = auth.get_password_hash(user.password)
        now = datetime.now(timezone.utc).isoformat() + "Z"
        
        db_query(conn,
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
        cur = db_query(conn,
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


def get_initial_rooms():
    import random
    # Direcciones disponibles desdel el pasillo (excepto sur que es inicio)
    dirs = ["north", "east", "west"]
    random.shuffle(dirs)
    
    # Asignar salas fijas a direcciones aleatorias
    exits_pasillo = {
        "south": "inicio",
        dirs[0]: "armeria",
        dirs[1]: "biblioteca",
        dirs[2]: "sala_guardia"
    }

    return {
        "inicio": {
            "name": "Habitación oscura",
            "description": "Estás en una habitación pequeña y oscura. Hay una puerta al norte.",
            "description_dark": "Todo está demasiado oscuro para ver algo. Solo intuyes una puerta al norte.",
            "exits": {"north": "pasillo"},
            "x": 0, "y": 0
        },
        "pasillo": {
            "name": "Pasillo de piedra",
            "description": "Te encuentras en un pasillo húmedo de piedra que se prolonga en varias direcciones.",
            "description_dark": "Notas un largo pasillo, pero apenas ves nada sin luz.",
            "exits": exits_pasillo,
            "x": 0, "y": 1
        },
        "armeria": {
            "name": "Armería",
            "description": "Una armería con estantes vacíos y el olor a metal oxidado.",
            "description_dark": "Sientes el frío de las paredes y el eco de un espacio grande.",
            "x": 0, "y": 2 if dirs[0] == "north" else 1, # Ajustar coord según dirección
            "exits": {llm_parser.DIRECTIONS_OPPOSITE.get(dirs[0], "south"): "pasillo", "north": "EMPTY", "east": "EMPTY", "west": "EMPTY"}
        },
        "biblioteca": {
            "name": "Biblioteca",
            "description": "Una biblioteca en ruinas, con libros esparcidos por el suelo y estanterías caídas.",
            "description_dark": "El aire es denso y huele a papel viejo y moho.",
            "x": -1 if dirs[1] == "west" else 1 if dirs[1] == "east" else 0,
            "y": 1 if dirs[1] != "north" else 2,
            "exits": {llm_parser.DIRECTIONS_OPPOSITE.get(dirs[1], "south"): "pasillo", "north": "EMPTY", "west": "EMPTY", "south": "EMPTY"}
        },
        "sala_guardia": {
            "name": "Sala de guardia",
            "description": "Una vieja sala de guardia con mesas volcadas y un arcón cerrado.",
            "description_dark": "Tropiezas con muebles en la oscuridad; parece una habitación amplia.",
            "x": 1 if dirs[2] == "east" else -1 if dirs[2] == "west" else 0,
            "y": 1 if dirs[2] != "north" else 2,
            "exits": {llm_parser.DIRECTIONS_OPPOSITE.get(dirs[2], "south"): "pasillo", "north": "EMPTY", "east": "EMPTY", "south": "EMPTY"},
            "victory_claimed": False
        },
    }

ROOMS = get_initial_rooms()

# Ruta para persistencia de salas procedimentales
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")

def load_rooms():
    global ROOMS
    if os.path.exists(ROOMS_FILE):
        try:
            with open(ROOMS_FILE, "r", encoding="utf-8") as f:
                ROOMS.update(json.load(f))
            logger.info(f"Salas cargadas desde {ROOMS_FILE}")
        except Exception as e:
            logger.error(f"Error cargando salas: {e}")


def get_history_context(journal: list) -> str:
    """Obtiene un resumen conciso del historial para el prompt."""
    if not journal:
        return "Inicio de la aventura."
    if len(journal) > 10:
        first = journal[:3]
        last = journal[-7:]
        return " | ".join(first) + " [...] " + " | ".join(last)
    return " | ".join(journal)

def save_rooms():
    """
    Guarda ROOMS en la base de datos en lugar de en un JSON local.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for room_id, data in ROOMS.items():
            db_query(conn, 
                "INSERT INTO dungeon_rooms (id, data_json) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json",
                (room_id, json.dumps(data, ensure_ascii=False))
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Error guardando salas en DB: {e}")
    finally:
        conn.close()

def load_rooms():
    """
    Carga ROOMS desde la base de datos. Si no hay nada, intenta migrar desde rooms.json.
    """
    global ROOMS
    conn = get_db_connection()
    try:
        cur = db_query(conn, "SELECT id, data_json FROM dungeon_rooms")
        rows = cur.fetchall()
        if rows:
            for row in rows:
                ROOMS[row[0]] = json.loads(row[1])
            logger.info(f"Cargadas {len(ROOMS)} salas desde la base de datos.")
            return

        # Si no hay salas en la DB, intentar migrar desde el archivo JSON si existe
        if os.path.exists(ROOMS_FILE):
            try:
                with open(ROOMS_FILE, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    ROOMS.update(file_data)
                logger.info(f"Migrando {len(ROOMS)} salas desde archivo JSON a la base de datos...")
                save_rooms() # Guardar en DB inmediatamente
            except Exception as e:
                logger.error(f"Error migrando rooms.json: {e}")
    except Exception as e:
        logger.error(f"Error cargando salas de la DB: {e}")
    finally:
        conn.close()

# Cargar salas al inicio
load_rooms()


def describe_room(state: dict, language: str = "es") -> str:
    room_id = str(state.get("room", "inicio"))
    room = ROOMS.get(room_id, ROOMS["inicio"])
    flashlight_on = bool(state.get("flashlight_on", False))

    if flashlight_on:
        base = str(room.get("description", "Una sala sin descripción."))
    else:
        base = str(room.get("description_dark", "Está demasiado oscuro para ver nada."))

    extra = ""
    inventory = state.get("inventory", [])
    if not isinstance(inventory, list):
        inventory = []

    if room_id == "inicio" and "flashlight" not in inventory:
        extra = "\nHay una linterna en el suelo." if flashlight_on else ""
        
    if room_id == "sala_guardia" and flashlight_on:
        if state.get("victory_claimed"):
            extra += " El arcón está abierto. Hay un túnel secreto aquí."
        else:
            extra += " Ves un arcón de madera con un candado oxidado."

    return base + extra


def add_journal_entry(state: dict, entry: str) -> None:
    """Añade una entrada al diario del estado si no es idéntica a la última."""
    journal = state.get("journal", [])
    if not isinstance(journal, list):
        journal = []
    if not journal or journal[-1] != entry:
        journal.append(entry)
    state["journal"] = journal


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
        "duration_ms": round(float(duration_ms), 2), # type: ignore
        "request_id": request_id,
        "client_hash": client_hash,
        "user_agent": request.headers.get("user-agent", ""),
    }
    logger.info(json.dumps(log_record, ensure_ascii=False))
    return response


def prefetch_rooms(state: dict, language: str):
    """
    Genera habitaciones adyacentes marcadas como EMPTY en segundo plano.
    """
    current_room_id = state.get("room", "inicio")
    current_room = ROOMS.get(current_room_id)
    if not current_room:
        return

    exits = current_room.get("exits", {})
    changed = False
    for direction, target in exits.items():
        if target == "EMPTY":
            curr_x = current_room.get("x", 0)
            curr_y = current_room.get("y", 0)
            new_x, new_y = curr_x, curr_y
            if direction == "north": new_y += 1
            elif direction == "south": new_y -= 1
            elif direction == "east": new_x += 1
            elif direction == "west": new_x -= 1
            
            new_room_id = f"proc_{new_x}_{new_y}"
            if new_room_id not in ROOMS:
                logger.info(f"Prefetch: Generando {new_room_id} en {direction}")
                new_room_data = llm_parser.generate_procedural_room(
                    current_room_desc=current_room.get("description", ""),
                    direction=direction,
                    language=language
                )
                if not new_room_data:
                    new_room_data = llm_parser.local_generate_room(direction, language=language)
                
                new_room_data["x"] = new_x
                new_room_data["y"] = new_y
                ROOMS[new_room_id] = new_room_data
            
            current_room["exits"][direction] = new_room_id
            changed = True
            
    if changed:
        save_rooms()

@app.post("/api/command", response_model=CommandResponse)
def process_command(body: CommandRequest, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    text = body.text.strip()
    global ROOMS
    raw_state = body.state or {"room": "inicio", "inventory": []}
    state = cast(Any, dict(raw_state))
    state["flashlight_on"] = bool(state.get("flashlight_on", False))
    
    # Asegurar que inventory y journal sean listas
    inv = state.get("inventory")
    state["inventory"] = list(inv) if isinstance(inv, list) else []
    
    state["game_won"] = bool(state.get("game_won", False))
    
    jrnl = state.get("journal")
    state["journal"] = list(jrnl) if isinstance(jrnl, list) else []
    target_lang = body.language

    # 1. Resolución de Idioma (Prioridad: Detección -> Estado -> Target -> Default)
    session_lang = state.get("language")
    new_detected = llm_parser.detect_language(text)
    
    # Lo que dice el LLM también cuenta (pero a veces falla)
    llm_lang = None # Inicializar aquí para que esté disponible antes del parse_command_llm
    
    # 1. Intentar parsear con LLM unificado
    # Le pasamos el idioma detectado por keywords si existe, si no "auto" para que el LLM detecte sin sesgos.
    llm_provisional_lang = new_detected or "auto"
    
    # 1. Resolución de historial
    history_str = get_history_context(state.get("journal", []))
    
    room_desc = describe_room(state, language=session_lang or "es") 
    llm_result = llm_parser.parse_command_llm(text, llm_provisional_lang, room_desc, history=history_str)
    
    # 1.1 Fallback local si el LLM falla o no está configurado
    if not llm_result:
        logger.info("Usando fallback local para el comando.")
        llm_result = llm_parser.local_parse_command(text, target_lang)
        
    intent = llm_result.get("intent") if llm_result else None
    slots = llm_result.get("slots", {}) if llm_result else {}
    llm_reply = llm_result.get("reply") if llm_result else None
    ambient_whisper = llm_result.get("ambient_whisper") if llm_result else None

    # Ahora que tenemos llm_result, podemos obtener llm_lang
    llm_lang = llm_result.get("language_code") if llm_result else None
    
    def normalize_lang(l):
        if not l or l in ["au", "no", "un"]: return None
        l = str(l).lower().strip()
        if l in llm_parser.LANGUAGE_ALIASES:
            return llm_parser.LANGUAGE_ALIASES[l]
        for code, name in llm_parser.LANG_MAP.items():
            if name.lower() in l:
                return code
        return l[:2]

    llm_lang = normalize_lang(llm_lang)
    target_lang = normalize_lang(target_lang)

    # Decidir el idioma final
    # 1. Si detectamos algo CLARO con keywords, es lo más fiable para el usuario
    if new_detected:
        detected_lang = new_detected
    # 2. Si el LLM detectó algo claro, lo usamos como segunda opción
    elif llm_lang and llm_lang not in ["au", "no", "un"]:
        detected_lang = llm_lang
    # 3. Si no, mantenemos el de la sesión
    elif session_lang:
        detected_lang = session_lang
    # 4. Si es la primera vez, miramos el 'target' del request
    elif target_lang and target_lang != "auto":
        detected_lang = target_lang
    # 5. Fallback final
    else:
        detected_lang = "es"

    # Persistir en el estado
    state["language"] = detected_lang

    logger.info(
        json.dumps(
            {
                "event": "command_received",
                "text": text,
                "user_id": user["id"],
                "language": detected_lang,
                "room": state.get("room", "inicio"),
            },
            ensure_ascii=False,
        )
    )

    reply = None

    # 2. Lógica de juego basada en Intent
    if intent == "help" or any(kw in text.lower() for kw in ["ayuda", "help", "aide", "hilfe", "aiuto", "ajuda", "ヘルプ"]):
        reply = llm_parser.HELP_MESSAGES.get(detected_lang, llm_parser.HELP_MESSAGES["es"])

    elif intent == "look" or "mirar" in text.lower():
        reply = describe_room(state, language=detected_lang)

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
                reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["pickup_flashlight"]
                
                # Registrar en diario
                room_name = state.get("room_name") or "una sala"
                add_journal_entry(state, f"Recogí la linterna en {room_name}")
            else:
                reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["already_have_flashlight"]
        else:
            reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["what_to_take"]

    elif intent == "toggle_light" or "linterna" in text.lower():
        # Asegurar que slots no sea None y que el valor no sea None
        action = (slots.get("action") or "").lower() if slots else ""
        has_flashlight = "flashlight" in state.get("inventory", [])
        
        if not has_flashlight:
            reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["no_flashlight"]
        else:
            # Detectar si quiere encender o apagar si el LLM no fue claro
            is_on = "encender" in text.lower() or "prender" in text.lower() or action == "on"
            is_off = "apagar" in text.lower() or action == "off"
            
            if is_on:
                if state.get("flashlight_on"):
                    reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["light_already_on"]
                else:
                    state["flashlight_on"] = True
                    reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["light_on"]
            elif is_off:
                if state.get("flashlight_on"):
                    state["flashlight_on"] = False
                    reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["light_off"]
                else:
                    reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["light_already_off"]

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
            
            prefix = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["inventory_prefix"]
            reply = prefix + ", ".join(items_localized)
        else:
            reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["inventory_empty"]

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

        if direction and direction in cast(dict[str, Any], current_room).get("exits", {}):
            new_room_id = cast(dict[str, Any], current_room)["exits"][direction]
            
            # PROCEDURAL GENERATION: Si la salida es EMPTY, generamos la sala con el LLM
            if new_room_id == "EMPTY":
                curr_x = current_room.get("x", 0)
                curr_y = current_room.get("y", 0)
                
                # Calcular nuevas coordenadas
                new_x, new_y = curr_x, curr_y
                if direction == "north": new_y += 1
                elif direction == "south": new_y -= 1
                elif direction == "east": new_x += 1
                elif direction == "west": new_x -= 1
                
                new_room_id = f"proc_{new_x}_{new_y}"
                
                # Si la sala ya existe (por otra conexión), la usamos
                if new_room_id in ROOMS:
                    current_room["exits"][direction] = new_room_id
                else:
                    new_room_data = llm_parser.generate_procedural_room(
                        current_room_desc=describe_room(state, language=detected_lang),
                        direction=direction,
                        language=detected_lang
                    )
                    
                    if not new_room_data:
                        logger.warning("Fallo en LLM procedimental, usando fallback local.")
                        new_room_data = llm_parser.local_generate_room(direction, language=detected_lang)
                    if new_room_data:
                        new_room_data["x"] = new_x
                        new_room_data["y"] = new_y
                        ROOMS[new_room_id] = new_room_data
                        current_room["exits"][direction] = new_room_id
                        save_rooms() # Persistir cambios
                    else:
                        # Fallback extremo si falla el LLM de generación
                        ROOMS[new_room_id] = {
                            "name": "Cámara Oscura",
                            "description": "Una sala genérica de piedra fría. El LLM está cansado.",
                            "x": new_x, "y": new_y,
                            "exits": {"south" if direction == "north" else "north" if direction == "south" else "west" if direction == "east" else "east": current_room_id}
                        }
                        current_room["exits"][direction] = new_room_id
                        save_rooms() # Persistir cambios

            state["room"] = new_room_id
            
            # Registrar en diario
            room_name = ROOMS.get(new_room_id, {}).get("name", "una nueva sala")
            add_journal_entry(state, f"Me moví al {direction} hacia {room_name}")
            
            # Actualizar coordenadas para el minimapa
            new_room_data = ROOMS.get(new_room_id, {})
            state["x"] = new_room_data.get("x", 0)
            state["y"] = new_room_data.get("y", 0)
            state["room_name"] = new_room_data.get("name", "Desconocido")
            
            reply = describe_room(state, language=detected_lang)
            
            # Hitos por habitación
            if new_room_id == "sala_guardia":
                msg = "Has descubierto una sala de guardia con muebles destrozados."
                if detected_lang != "es":
                    msg = llm_parser.translate_reply(msg, detected_lang)
                add_journal_entry(state, msg)
        else:
            reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["no_path"]

    elif intent == "open_door" or "abrir puerta" in text.lower() or "abrir arcon" in text.lower() or "abrir arcón" in text.lower():
        current_room_id = state.get("room", "inicio")
        if current_room_id == "inicio":
            state["room"] = "pasillo"
            # Actualizar coordenadas para el minimapa
            new_room_data = ROOMS.get("pasillo", {})
            state["x"] = new_room_data.get("x", 0)
            state["y"] = new_room_data.get("y", 0)
            state["room_name"] = new_room_data.get("name", "Pasillo de piedra")
            
            msg = "Has logrado abrir la puerta de tu celda y salir al pasillo."
            if detected_lang != "es":
                msg = llm_parser.translate_reply(msg, detected_lang)
            add_journal_entry(state, msg)
            
            door_msg = "Abres la puerta con esfuerzo. Cruzas al pasillo."
            if detected_lang != "es":
                door_msg = llm_parser.translate_reply(door_msg, detected_lang)
                
            reply = door_msg + "\n" + describe_room(state, language=detected_lang)
        elif text.lower() in ["reset", "reiniciar", "limpiar"]:
            # Borrar mundo procedural
            if os.path.exists(ROOMS_FILE):
                try:
                    os.remove(ROOMS_FILE)
                    logger.info("Archivo rooms.json eliminado en reset.")
                except Exception as e:
                    logger.error(f"Error eliminando rooms.json: {e}")
            
            ROOMS = get_initial_rooms()
            
            state = {"room": "inicio", "inventory": [], "journal": [], "language": detected_lang}
            msg = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["reset_world"]
            add_journal_entry(state, msg)
            reply = msg
            return CommandResponse(reply=reply, state=state, detected_language=detected_lang or "es")

        elif current_room_id == "sala_guardia":
            if state.get("flashlight_on"):
                if not state.get("victory_claimed"):
                    state["victory_claimed"] = True
                    add_journal_entry(state, "¡Has encontrado la salida secreta!")
                    reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["victory"]
                else:
                    reply = describe_room(state, language=detected_lang)
            else:
                reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["too_dark"]
        else:
            reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["nothing_to_open"]

    # 4. Respuesta final: Priorizamos 'reply' (lógica de juego) si existe.
    if reply:
        # Solo omitimos la traducción si el mensaje ya está en el idioma correcto
        already_localized = False
        
        # Comprobar en MESSAGES del idioma actual
        current_lang_msgs = llm_parser.MESSAGES.get(detected_lang, {})
        if reply in current_lang_msgs.values():
            already_localized = True
            
        # Comprobar en HELP_MESSAGES del idioma actual
        if not already_localized:
            current_help = llm_parser.HELP_MESSAGES.get(detected_lang)
            if reply == current_help:
                already_localized = True
        
        if already_localized:
            final_reply = reply
        else:
            # Si el mensaje vino de un fallback en español o es dinámico, lo traducimos
            final_reply = llm_parser.translate_reply(reply, detected_lang)
    elif llm_reply and intent != "unknown":
        final_reply = llm_reply
    else:
        # Fallback genérico
        final_reply = llm_parser.MESSAGES.get(detected_lang, llm_parser.MESSAGES["es"])["fallback"]

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

    # Incluir salidas actuales para el minimapa
    current_room_id = state.get("room", "inicio")
    state["room_exits"] = ROOMS.get(current_room_id, {}).get("exits", {})

    # Disparar pre-fetching de salas adyacentes en segundo plano
    background_tasks.add_task(prefetch_rooms, state, detected_lang)

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
        db_query(conn,
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
        cur = db_query(conn, "SELECT state_json, user_id FROM saves WHERE id = ?", (save_id,))
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

