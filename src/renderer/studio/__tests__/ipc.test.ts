import { afterEach, describe, expect, it } from "vitest";
import type { StudioApi } from "../../../shared/contract/studio-api";
import { createIpcStudio } from "../ipc";

const setPreload = (studio: StudioApi | undefined) =>
  Object.defineProperty(window, "studio", {
    value: studio,
    configurable: true,
  });

afterEach(() => {
  setPreload(undefined);
});

describe("createIpcStudio", () => {
  it("returns the preload's window.studio", () => {
    const studio: StudioApi = {
      versions: { electron: "e", chrome: "c", node: "n" },
    };
    setPreload(studio);
    expect(createIpcStudio()).toBe(studio);
  });

  it("throws when the preload did not load, instead of falling back", () => {
    expect(() => createIpcStudio()).toThrow(
      "Preload failed: window.studio is missing.",
    );
  });
});
