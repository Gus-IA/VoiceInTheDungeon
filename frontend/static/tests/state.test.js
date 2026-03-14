import { describe, it, expect, beforeEach } from "vitest";
import { saveGameState, loadGameState } from "../state";
describe("state persistence helpers", () => {
    beforeEach(() => {
        const store = {};
        global.localStorage = {
            getItem(key) {
                var _a;
                return (_a = store[key]) !== null && _a !== void 0 ? _a : null;
            },
            setItem(key, value) {
                store[key] = value;
            },
            removeItem(key) {
                delete store[key];
            },
            clear() {
                Object.keys(store).forEach((k) => delete store[k]);
            },
        };
    });
    it("saves and loads a game state roundtrip", () => {
        const state = {
            room: "inicio",
            inventory: ["flashlight"],
            flashlight_on: true,
        };
        const saved = saveGameState(state);
        expect(saved).toBe(true);
        const loaded = loadGameState();
        expect(loaded).not.toBeNull();
        expect(loaded === null || loaded === void 0 ? void 0 : loaded.room).toBe("inicio");
        expect(loaded === null || loaded === void 0 ? void 0 : loaded.inventory).toContain("flashlight");
        expect(loaded === null || loaded === void 0 ? void 0 : loaded.flashlight_on).toBe(true);
    });
    it("fails gracefully when there is nothing to load", () => {
        const loaded = loadGameState();
        expect(loaded).toBeNull();
    });
});
