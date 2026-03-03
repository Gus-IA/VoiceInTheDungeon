var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { saveGameState, loadGameState } from "./state.js";
const logDiv = document.getElementById("log");
const speakBtn = document.getElementById("speakBtn");
const statusDiv = document.getElementById("status");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");
const saveBtn = document.getElementById("saveBtn");
const loadBtn = document.getElementById("loadBtn");
let state = null;
let recognizing = false;
function appendLog(who, text) {
    if (!logDiv)
        return;
    const prefix = who === "tú" ? "👤 " : "🧙 ";
    logDiv.textContent += `${prefix}${text}\n`;
    logDiv.scrollTop = logDiv.scrollHeight;
}
function setStatus(text) {
    if (!statusDiv)
        return;
    statusDiv.textContent = text;
}
function speakText(text) {
    if (!("speechSynthesis" in window))
        return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-ES";
    window.speechSynthesis.speak(utterance);
}
function sendCommand(text) {
    return __awaiter(this, void 0, void 0, function* () {
        appendLog("tú", text);
        try {
            const res = yield fetch("/api/command", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, state }),
            });
            if (!res.ok) {
                throw new Error(`Error HTTP: ${res.status}`);
            }
            const data = (yield res.json());
            state = data.state;
            appendLog("juego", data.reply);
            speakText(data.reply);
        }
        catch (err) {
            console.error(err);
            appendLog("juego", "Hay un problema al hablar con el servidor.");
        }
    });
}
if (saveBtn) {
    saveBtn.onclick = () => {
        if (!state) {
            setStatus("No hay partida que guardar todavía.");
            return;
        }
        const ok = saveGameState(state);
        if (ok) {
            setStatus("Partida guardada en este navegador.");
        }
        else {
            setStatus("No se ha podido guardar la partida.");
        }
    };
}
if (loadBtn) {
    loadBtn.onclick = () => {
        const loaded = loadGameState();
        if (!loaded) {
            setStatus("No se ha encontrado ninguna partida guardada.");
            return;
        }
        state = loaded;
        appendLog("juego", "Has cargado una partida guardada.");
        // Forzamos una descripción de la sala actual con el estado cargado
        sendCommand("mirar");
    };
}
function setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        setStatus("Tu navegador no soporta Web Speech API. Prueba con Chrome.");
        if (speakBtn)
            speakBtn.disabled = true;
        return null;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "es-ES";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
        recognizing = true;
        if (speakBtn)
            speakBtn.textContent = "Escuchando...";
        setStatus("Escuchando, habla ahora...");
    };
    recognition.onend = () => {
        recognizing = false;
        if (speakBtn)
            speakBtn.textContent = "🎙️ Hablar";
        setStatus("");
    };
    recognition.onerror = (event) => {
        console.error("Speech error", event.error);
        setStatus(`Error de voz: ${event.error}`);
    };
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        sendCommand(transcript);
    };
    return recognition;
}
const recognition = setupSpeechRecognition();
if (recognition && speakBtn) {
    speakBtn.onclick = () => {
        if (recognizing) {
            recognition.stop();
        }
        else {
            recognition.start();
        }
    };
}
if (sendBtn && textInput) {
    const sendText = () => {
        const value = textInput.value.trim();
        if (!value)
            return;
        sendCommand(value);
        textInput.value = "";
    };
    sendBtn.onclick = sendText;
    textInput.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
            ev.preventDefault();
            sendText();
        }
    });
}
