import { GameState, saveGameState, loadGameState } from "./state.js";

const logDiv = document.getElementById("log") as HTMLDivElement | null;
const speakBtn = document.getElementById("speakBtn") as HTMLButtonElement | null;
const statusDiv = document.getElementById("status") as HTMLDivElement | null;
const textInput = document.getElementById("textInput") as HTMLInputElement | null;
const sendBtn = document.getElementById("sendBtn") as HTMLButtonElement | null;
// PRE-CARGAR VOCES PARA EVITAR RETRASOS
let voicesLoaded = false;
const preloadVoices = () => {
  if (window.speechSynthesis.getVoices().length > 0) {
    voicesLoaded = true;
    window.speechSynthesis.removeEventListener("voiceschanged", preloadVoices);
  }
};
if (window.speechSynthesis.onvoiceschanged !== undefined) {
  window.speechSynthesis.addEventListener("voiceschanged", preloadVoices);
}
preloadVoices();
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
const journalContainer = document.getElementById("journal-container") as HTMLDivElement | null;
const journalList = document.getElementById("journal-list") as HTMLUListElement | null;
let isLoginMode = true;

// Idioma del navegador como fallback
const browserLang = navigator.language.split("-")[0] || "es";

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
  
  entry.append(meta, body);
  logDiv.appendChild(entry);
  logDiv.scrollTop = logDiv.scrollHeight;

  if (isPlayer) {
    body.textContent = text;
  } else {
    body.textContent = "";
    let i = 0;
    function typeChar() {
      if (i < text.length) {
        body.textContent += text.charAt(i);
        i++;
        if (logDiv) logDiv.scrollTop = logDiv.scrollHeight;
        setTimeout(typeChar, 15);
      }
    }
    typeChar();
  }
}

function setStatus(msg: string) {
  if (statusDiv) statusDiv.textContent = msg;
}

function renderJournal() {
  if (!journalContainer || !journalList || !state) return;
  const journalEntries = state.journal || [];
  
  if (journalEntries.length === 0) {
    journalContainer.style.display = "none";
    return;
  }
  
  journalContainer.style.display = "block";
  journalList.innerHTML = "";
  journalEntries.forEach(entry => {
    const li = document.createElement("li");
    li.textContent = entry;
    journalList.appendChild(li);
  });
}

interface SpeakOptions {
  pitch?: number;
  rate?: number;
  voiceName?: string;
}

function speakText(text: string, options: { pitch?: number, rate?: number, lang?: string, voiceName?: string, onEnd?: () => void } = {}) {
  if (!text) {
    options.onEnd?.();
    return;
  }
  const synth = window.speechSynthesis;
  if (!synth) {
    options.onEnd?.();
    return;
  }

  // Mapeo select value -> BCP 47
  const langMap: Record<string, string> = {
    "es": "es-ES",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "pt": "pt-PT",
    "hi": "hi-IN"
  };

  const startSpeak = () => {
    const utterance = new SpeechSynthesisUtterance(text);
    
    let targetCode = options.lang || browserLang || "es";
    if (targetCode === "auto") {
      targetCode = navigator.language.split("-")[0] || "es";
    }

    const bcp47 = langMap[targetCode] || targetCode;
    const prefix = bcp47.split("-")[0].toLowerCase();
    utterance.pitch = options.pitch ?? 1.0;
    utterance.rate = options.rate ?? 1.0;
    utterance.lang = bcp47;

    // === SELECCIÓN DE VOZ NATIVA ===
    const voices = synth.getVoices();
    console.log(`[VOICE] Target: ${bcp47} (prefix: ${prefix}), Available voices: ${voices.length}`);
    
    if (options.voiceName) {
      const v = voices.find(v => v.name.includes(options.voiceName!));
      if (v) utterance.voice = v;
    } else if (voices.length > 0) {
      let bestVoice: SpeechSynthesisVoice | null = null;
      let bestScore = -1;

      for (const v of voices) {
        const vLang = v.lang.toLowerCase();
        const vPrefix = vLang.split("-")[0];
        let score = 0;

        if (vPrefix !== prefix) continue;

        score += 10;
        if (vLang === bcp47.toLowerCase()) score += 5;
        if (v.localService) score += 3;
        if (v.name.toLowerCase().includes("google")) score += 2;

        if (score > bestScore) {
          bestScore = score;
          bestVoice = v;
        }
      }

      if (bestVoice) {
        utterance.voice = bestVoice;
        utterance.lang = bestVoice.lang;
        console.log(`[VOICE] ✅ Selected: "${bestVoice.name}" (${bestVoice.lang}), score=${bestScore}`);
      } else {
        // No hay voz nativa para este idioma.
        // NO asignar utterance.voice para que Chrome use su TTS online con el lang correcto.
        console.log(`[VOICE] ⚠️ No native voice for "${prefix}". Using browser default TTS with lang=${bcp47}`);
        // Listar qué idiomas SÍ tienen voces disponibles
        const availableLangs = [...new Set(voices.map(v => v.lang.split("-")[0]))];
        console.log(`[VOICE] Available language prefixes: ${availableLangs.join(", ")}`);
      }
    } else {
      console.log("[VOICE] ⚠️ No voices loaded at all!");
    }

    utterance.onend = () => {
      options.onEnd?.();
    };
    utterance.onerror = () => {
      options.onEnd?.();
    };

    synth.speak(utterance);
  };

  // Si las voces ya están listas, hablamos. Si no, esperamos una sola vez.
  if (voicesLoaded || synth.getVoices().length > 0) {
    startSpeak();
  } else {
    const onReady = () => {
      synth.removeEventListener("voiceschanged", onReady);
      voicesLoaded = true;
      startSpeak();
    };
    synth.addEventListener("voiceschanged", onReady);
    setTimeout(startSpeak, 1500); // Fail-safe
  }
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
        language: "auto" 
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
    renderJournal();
    appendLog("juego", data.reply);

    // Cancelar cualquier audio anterior antes de empezar el nuevo bloque
    window.speechSynthesis.cancel();

    // DETERMINAR IDIOMA PARA VOZ
    const voiceLang = data.detected_language || browserLang || "es";

    // Narrar respuesta
    speakText(data.reply, { 
      lang: voiceLang
    });

    // Detección de Victoria (Visual)
    if (state && (state as any).game_won) {
      appendLog("juego", "✨ ¡VICTORIA! ✨");
    }
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
          renderJournal();
          appendLog("juego", "Cargada del servidor.");
          sendCommand("mirar");
          return;
        }
      } catch (err) { console.error(err); }
    }
    const loaded = loadGameState();
    if (loaded) {
      state = loaded;
      renderJournal();
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

// Visualizer Setup
let audioCtx: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let audioSource: MediaStreamAudioSourceNode | null = null;
let visualizerReqId: number = 0;
const visualizerCanvas = document.getElementById("visualizer") as HTMLCanvasElement | null;
let visualizerCtx: CanvasRenderingContext2D | null = null;
if (visualizerCanvas) {
  visualizerCtx = visualizerCanvas.getContext("2d");
}

function drawVisualizer() {
  if (!analyser || !visualizerCtx || !visualizerCanvas) return;
  
  visualizerReqId = requestAnimationFrame(drawVisualizer);
  
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(dataArray);

  visualizerCtx.fillStyle = "#0f172a";
  visualizerCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

  const barWidth = (visualizerCanvas.width / bufferLength) * 2.5;
  let barHeight;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    barHeight = dataArray[i] / 2;
    const h = Math.max(2, barHeight / 2);
    visualizerCtx.fillStyle = `rgb(34, ${barHeight + 100}, 94)`;
    visualizerCtx.fillRect(x, visualizerCanvas.height - h, barWidth, h);
    x += barWidth + 1;
  }
}


async function setupWhisper() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setStatus("Navegador no soporta audio.");
    if (speakBtn) speakBtn.disabled = true;
    return;
  }

  const start = async () => {
    if (recognizing) return;
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      analyser = audioCtx.createAnalyser();
      audioSource = audioCtx.createMediaStreamSource(stream);
      audioSource.connect(analyser);
      analyser.fftSize = 256;

      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstart = () => {
        recognizing = true;
        if (speakBtn) {
            speakBtn.textContent = "Grabando...";
            speakBtn.classList.add("is-listening");
        }
        if (visualizerCanvas) {
            visualizerCanvas.style.display = "block";
            drawVisualizer();
        }
        setStatus("Escuchando... suelta para enviar");
      };
      mediaRecorder.onstop = async () => {
        recognizing = false;
        if (visualizerReqId) cancelAnimationFrame(visualizerReqId);
        if (visualizerCanvas) {
          visualizerCanvas.style.display = "none";
          visualizerCtx?.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
        }

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
