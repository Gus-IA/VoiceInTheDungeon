const SAVE_KEY = "voice-in-the-dungeon-save-1";
export function saveGameState(state) {
    if (!state) {
        return false;
    }
    try {
        localStorage.setItem(SAVE_KEY, JSON.stringify(state));
        return true;
    }
    catch (_a) {
        return false;
    }
}
export function loadGameState() {
    try {
        const raw = localStorage.getItem(SAVE_KEY);
        if (!raw)
            return null;
        return JSON.parse(raw);
    }
    catch (_a) {
        return null;
    }
}
