import { GameState, saveGameState, loadGameState } from "./state.js";

const logDiv = document.getElementById("log") as HTMLDivElement | null;
const speakBtn = document.getElementById("speakBtn") as HTMLButtonElement | null;
const statusDiv = document.getElementById("status") as HTMLDivElement | null;
const textInput = document.getElementById("textInput") as HTMLInputElement | null;
const sendBtn = document.getElementById("sendBtn") as HTMLButtonElement | null;
const saveBtn = document.getElementById("saveBtn") as HTMLButtonElement | null;
const loadBtn = document.getElementById("loadBtn") as HTMLButtonElement | null;

let state: GameState | null = null;
let recognizing = false;
let token: string | null = localStorage.getItem("vitd-token");

const LAST_SAVE_ID_KEY = "voice-in-the-dungeon-last-save-id";

// UI Elements
const loginModal = document.getElementById("loginModal") as HTMLDivElement | null;
const gameUI = document.getElementById("gameUI") as HTMLDivElement | null;
const authStatus = document.getElementById("authStatus") as HTMLDivElement | null;
const logoutBtn = document.getElementById("logoutBtn") as HTMLButtonElement | null;
const authBtn = document.getElementById("authBtn") as HTMLButtonElement | null;
const toggleAuthMode = document.getElementById("toggleAuthMode") as HTMLButtonElement | null;
const usernameInput = document.getElementById("usernameInput") as HTMLInputElement | null;
const passwordInput = document.getElementById("passwordInput") as HTMLInputElement | null;
const authMsg = document.getElementById("authMsg") as HTMLDivElement | null;
const modalTitle = document.getElementById("modalTitle") as HTMLHeadingElement | null;
const langSelect = document.getElementById("langSelect") as HTMLSelectElement | null;

let isLoginMode = true;

// Detectar idioma del navegador/sistema
const browserLang = navigator.language.split("-")[0];
if (langSelect) {
  const supportedLangs = ["es", "en", "fr", "de", "it", "pt"];
  if (supportedLangs.indexOf(browserLang) !== -1) {
    langSelect.value = browserLang;
  }
}

function updateAuthUI() {
  if (token) {
    if (loginModal) loginModal.style.display = "none";
    if (gameUI) gameUI.style.display = "block";
    if (logoutBtn) logoutBtn.style.display = "inline-flex";
    if (authStatus) {
      authStatus.textContent = "🧙 Sesión iniciada";
    }
  } else {
    if (loginModal) loginModal.style.display = "flex";
    if (gameUI) gameUI.style.display = "none";
    if (logoutBtn) logoutBtn.style.display = "none";
    if (authStatus) authStatus.textContent = "";
  }
}

if (toggleAuthMode) {
  toggleAuthMode.onclick = () => {
    isLoginMode = !isLoginMode;
    if (modalTitle) modalTitle.textContent = isLoginMode ? "Entrar al calabozo" : "Crear cuenta";
    if (authBtn) authBtn.textContent = isLoginMode ? "Entrar" : "Registrarse";
    if (toggleAuthMode) toggleAuthMode.textContent = isLoginMode ? "¿No tienes cuenta? Regístrate" : "¿Ya tienes cuenta? Entra";
  };
}

if (authBtn) {
  authBtn.onclick = async () => {
    const username = usernameInput?.value;
    const password = passwordInput?.value;
    if (!username || !password) return;
    if (authMsg) authMsg.textContent = "Procesando...";

    try {
      if (isLoginMode) {
        const formData = new FormData();
        formData.append("username", username);
        formData.append("password", password);
        const res = await fetch("/api/login", { method: "POST", body: formData });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || "Error al entrar");
        }
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem("vitd-token", token!);
        updateAuthUI();
      } else {
        const res = await fetch("/api/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || "Error al registrar");
        }
        if (authMsg) {
          authMsg.textContent = "Registro con éxito. Ahora puedes entrar.";
          authMsg.style.color = "#22c55e";
        }
        isLoginMode = true;
        if (modalTitle) modalTitle.textContent = "Entrar al calabozo";
        if (authBtn) authBtn.textContent = "Entrar";
        if (toggleAuthMode) toggleAuthMode.textContent = "¿No tienes cuenta? Regístrate";
      }
    } catch (err: any) {
      if (authMsg) {
        authMsg.textContent = err.message;
        authMsg.style.color = "#ef4444";
      }
    }
  };
}

if (logoutBtn) {
  logoutBtn.onclick = () => {
    token = null;
    localStorage.removeItem("vitd-token");
    updateAuthUI();
  };
}

updateAuthUI();

function formatLogTime(): string {
  const now = new Date();
  return now.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function appendLog(who: "tú" | "juego", text: string) {
  if (!logDiv) return;
  const isPlayer = who === "tú";
  if (isPlayer && logDiv.children.length > 0) {
    const sep = document.createElement("div");
    sep.className = "log-sep";
    sep.setAttribute("aria-hidden", "true");
    logDiv.appendChild(sep);
  }
  const entry = document.createElement("div");
  entry.className = `log-entry log-entry--${isPlayer ? "player" : "game"}`;
  entry.setAttribute("role", "listitem");
  const time = document.createElement("span");
  time.className = "log-time";
  time.textContent = formatLogTime();
  const icon = document.createElement("span");
  icon.className = "log-icon";
  icon.textContent = isPlayer ? "👤" : "🧙";
  const meta = document.createElement("span");
  meta.className = "log-meta";
  meta.append(time, icon);
  const body = document.createElement("span");
  body.className = "log-text";
  body.textContent = text;
  entry.append(meta, body);
  logDiv.appendChild(entry);
  logDiv.scrollTop = logDiv.scrollHeight;
}

function setStatus(text: string) {
  if (!statusDiv) return;
  statusDiv.textContent = text;
}

function speakText(text: string) {
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = langSelect?.value || "es";
  window.speechSynthesis.speak(utterance);
}

async function sendCommand(text: string) {
  if (!token) return;
  appendLog("tú", text);
  try {
    const res = await fetch("/api/command", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ 
        text, 
        state, 
        language: langSelect?.value || "es" 
      }),
    });
    if (res.status === 401) {
      token = null;
      localStorage.removeItem("vitd-token");
      updateAuthUI();
      return;
    }
    if (!res.ok) throw new Error(`Error HTTP: ${res.status}`);
    const data = await res.json();
    state = data.state;
    appendLog("juego", data.reply);
    speakText(data.reply);
  } catch (err) {
    console.error(err);
    appendLog("juego", "Hay un problema al hablar con el servidor.");
  }
}

if (saveBtn) {
  saveBtn.onclick = async () => {
    if (!state) {
      setStatus("No hay partida que guardar todavía.");
      return;
    }
    const ok = saveGameState(state);
    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ state }),
      });
      if (res.status === 401) {
        token = null;
        localStorage.removeItem("vitd-token");
        updateAuthUI();
        return;
      }
      if (!res.ok) throw new Error(`Error HTTP al guardar: ${res.status}`);
      const data = await res.json();
      window.localStorage.setItem(LAST_SAVE_ID_KEY, data.save_id);
      setStatus(`Partida guardada en el servidor. ID: ${data.save_id}`);
    } catch (err) {
      console.error(err);
      setStatus(ok ? "Guardado local OK, servidor falló." : "Error total al guardar.");
    }
  };
}

if (loadBtn) {
  loadBtn.onclick = async () => {
    const lastSaveId = window.localStorage.getItem(LAST_SAVE_ID_KEY);
    if (lastSaveId) {
      try {
        const res = await fetch(`/api/save/${encodeURIComponent(lastSaveId)}`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.status === 401) {
          token = null;
          localStorage.removeItem("vitd-token");
          updateAuthUI();
          return;
        }
        if (res.ok) {
          const data = await res.json();
          state = data.state;
          appendLog("juego", "Cargada del servidor.");
          sendCommand("mirar");
          return;
        }
      } catch (err) { console.error(err); }
    }
    const loaded = loadGameState();
    if (loaded) {
      state = loaded;
      appendLog("juego", "Cargada local.");
      sendCommand("mirar");
    } else {
      setStatus("No hay partidas guardadas.");
    }
  };
}

// Whisper
let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];

async function setupWhisper() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setStatus("Navegador no soporta audio.");
    if (speakBtn) speakBtn.disabled = true;
    return;
  }

  const start = async () => {
    if (recognizing) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstart = () => {
        recognizing = true;
        if (speakBtn) {
            speakBtn.textContent = "Grabando...";
            speakBtn.classList.add("is-listening");
        }
        setStatus("Escuchando... suelta para enviar");
      };
      mediaRecorder.onstop = async () => {
        recognizing = false;
        if (speakBtn) {
            speakBtn.textContent = "🎙️ Hablar";
            speakBtn.classList.remove("is-listening");
        }
        setStatus("Procesando voz...");
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", audioBlob, "audio.webm");
        try {
          const res = await fetch("/api/transcribe", {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData
          });
          if (res.ok) {
            const data = await res.json();
            if (data.text) sendCommand(data.text);
          } else { setStatus("Error transcripción."); }
        } catch (err) { setStatus("Error de conexión voz."); }
        finally { setStatus(""); }
      };
      mediaRecorder.start();
    } catch (err) { setStatus("Error micrófono."); }
  };

  const stop = () => {
    if (recognizing && mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  };

  if (speakBtn) {
    // Soporte para PC (Mouse)
    speakBtn.addEventListener("mousedown", (e) => { e.preventDefault(); start(); });
    speakBtn.addEventListener("mouseup", stop);
    speakBtn.addEventListener("mouseleave", stop);

    // Soporte para Móvil (Touch)
    speakBtn.addEventListener("touchstart", (e) => { e.preventDefault(); start(); });
    speakBtn.addEventListener("touchend", stop);
  }
}

setupWhisper();

if (sendBtn && textInput) {
  const sendText = () => {
    const val = textInput.value.trim();
    if (!val) return;
    sendCommand(val);
    textInput.value = "";
  };
  sendBtn.onclick = sendText;
  textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); sendText(); }
  });
}
