export type GameState = {
  room: string;
  inventory: string[];
  flashlight_on?: boolean;
};

const SAVE_KEY = "voice-in-the-dungeon-save-1";

export function saveGameState(state: GameState | null): boolean {
  if (!state) {
    return false;
  }
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function loadGameState(): GameState | null {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as GameState;
  } catch {
    return null;
  }
}

