import { describe, expect, it, vi } from "vitest";
import type { StudioApi } from "../../../shared/contract/studio-api";

const fake = (electron: string): StudioApi => ({
  versions: { electron, chrome: "c", node: "n" },
});

// A fresh module per test: the installed adapter is module state.
const load = async () => {
  vi.resetModules();
  return import("../studio");
};

describe("getStudio", () => {
  it("throws before an adapter is installed", async () => {
    const { getStudio } = await load();
    expect(() => getStudio()).toThrow(/not installed/);
  });

  it("returns the installed adapter", async () => {
    const { getStudio, installStudio } = await load();
    const api = fake("1");
    installStudio(api);
    expect(getStudio()).toBe(api);
  });

  it("returns the latest adapter when tests install another", async () => {
    const { getStudio, installStudio } = await load();
    installStudio(fake("1"));
    const second = fake("2");
    installStudio(second);
    expect(getStudio()).toBe(second);
  });
});
