import { describe, it, expect, beforeEach } from "vitest";
import { saveGameState, loadGameState, GameState } from "../state";

declare const global: any;

describe("state persistence helpers", () => {
  beforeEach(() => {
    const store: Record<string, string> = {};
    global.localStorage = {
      getItem(key: string) {
        return store[key] ?? null;
      },
      setItem(key: string, value: string) {
        store[key] = value;
      },
      removeItem(key: string) {
        delete store[key];
      },
      clear() {
        Object.keys(store).forEach((k) => delete store[k]);
      },
    };
  });

  it("saves and loads a game state roundtrip", () => {
    const state: GameState = {
      room: "inicio",
      inventory: ["flashlight"],
      flashlight_on: true,
    };

    const saved = saveGameState(state);
    expect(saved).toBe(true);

    const loaded = loadGameState();
    expect(loaded).not.toBeNull();
    expect(loaded?.room).toBe("inicio");
    expect(loaded?.inventory).toContain("flashlight");
    expect(loaded?.flashlight_on).toBe(true);
  });

  it("fails gracefully when there is nothing to load", () => {
    const loaded = loadGameState();
    expect(loaded).toBeNull();
  });
});

