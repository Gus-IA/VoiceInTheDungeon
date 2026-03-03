from pathlib import Path
import json
import logging
from time import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


logger = logging.getLogger("voice_in_the_dungeon")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, limita los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend estático desde / y /static
PROJECT_ROOT = Path(__file__).parent.parent
STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


class CommandRequest(BaseModel):
    text: str
    state: dict | None = None


class CommandResponse(BaseModel):
    reply: str
    state: dict


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
    room_id = state.get("room", "inicio")
    room = ROOMS.get(room_id, ROOMS["inicio"])
    flashlight_on = state.get("flashlight_on", False)

    base = room["description"] if flashlight_on else room["description_dark"]

    extra = ""
    if room_id == "inicio" and "flashlight" not in state.get("inventory", []):
        extra = " En el suelo distingues la silueta de una linterna."
    if room_id == "sala_guardia" and flashlight_on:
        extra += " Ves un arcón de madera con un candado oxidado."

    return base + extra


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time()
    response = await call_next(request)
    duration_ms = (time() - start) * 1000

    log_record = {
        "event": "http_request",
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 2),
    }
    logger.info(json.dumps(log_record, ensure_ascii=False))
    return response


@app.post("/api/command", response_model=CommandResponse)
def process_command(body: CommandRequest):
    text = body.text.lower()
    state = body.state or {"room": "inicio", "inventory": []}
    state.setdefault("flashlight_on", False)

    logger.info(
        json.dumps(
            {
                "event": "command_received",
                "text": text,
                "room": state.get("room", "inicio"),
                "inventory": state.get("inventory", []),
                "flashlight_on": state.get("flashlight_on", False),
            },
            ensure_ascii=False,
        )
    )

    # Ayuda
    if "ayuda" in text or "help" in text:
        reply = (
            "Puedes decir cosas como: 'mirar', 'coger linterna', "
            "'inventario', 'encender linterna', 'apagar linterna', "
            "'ir norte/sur/este/oeste' o 'abrir puerta'."
        )

    # Mirar alrededor
    elif "mirar" in text or "look" in text:
        reply = describe_room(state)

    # Coger linterna
    elif "coger linterna" in text or "take flashlight" in text:
        if "flashlight" not in state["inventory"]:
            state["inventory"].append("flashlight")
            reply = "Coges la linterna. Te sientes un poco más seguro."
        else:
            reply = "Ya tienes la linterna."

    # Encender / apagar linterna
    elif ("encender" in text or "prender" in text) and "linterna" in text:
        if "flashlight" in state["inventory"]:
            if state["flashlight_on"]:
                reply = "La linterna ya está encendida."
            else:
                state["flashlight_on"] = True
                reply = "Enciendes la linterna. La oscuridad retrocede a tu alrededor."
        else:
            reply = "No tienes ninguna linterna que encender."

    elif "apagar" in text and "linterna" in text:
        if state["flashlight_on"]:
            state["flashlight_on"] = False
            reply = "Apagas la linterna. La oscuridad vuelve a envolverte."
        else:
            reply = "La linterna ya está apagada."

    # Inventario
    elif "inventario" in text or "inventory" in text:
        if state["inventory"]:
            reply = "Llevas: " + ", ".join(state["inventory"])
        else:
            reply = "No llevas nada."

    # Moverse por direcciones
    elif "norte" in text or "sur" in text or "este" in text or "oeste" in text:
        current_room_id = state.get("room", "inicio")
        current_room = ROOMS.get(current_room_id, ROOMS["inicio"])

        direction = None
        for d in ["norte", "sur", "este", "oeste"]:
            if d in text:
                direction = d
                break

        if direction and direction in current_room["exits"]:
            new_room_id = current_room["exits"][direction]
            state["room"] = new_room_id
            reply = describe_room(state)
        else:
            reply = "No parece haber ningún camino en esa dirección."

    # Abrir puerta (alias para ir norte desde la habitación inicial)
    elif "abrir puerta" in text or ("abrir" in text and "puerta" in text):
        if state.get("room", "inicio") == "inicio":
            state["room"] = "pasillo"
            reply = (
                "Abres la puerta con esfuerzo. Cruzas al pasillo.\n" + describe_room(state)
            )
        else:
            reply = "No ves ninguna puerta que puedas abrir aquí."

    else:
        reply = "No entiendo lo que intentas hacer. Di 'ayuda' para ver opciones."

    logger.info(
        json.dumps(
            {
                "event": "command_result",
                "text": text,
                "reply": reply,
                "room": state.get("room", "inicio"),
                "inventory": state.get("inventory", []),
                "flashlight_on": state.get("flashlight_on", False),
            },
            ensure_ascii=False,
        )
    )

    return CommandResponse(reply=reply, state=state)

