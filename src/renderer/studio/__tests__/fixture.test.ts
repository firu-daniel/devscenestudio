import { describe, expect, it } from "vitest";
import { createFixtureStudio } from "../fixture";
import { scenarios } from "../fixtures";

describe("createFixtureStudio", () => {
  it("plays the default scenario when ?scenario= is absent", () => {
    expect(createFixtureStudio("").versions).toEqual(
      scenarios.default!.versions,
    );
    expect(createFixtureStudio("?speed=0").versions).toEqual(
      scenarios.default!.versions,
    );
  });

  it("plays the scenario named in ?scenario=", () => {
    expect(createFixtureStudio("?scenario=default").versions).toEqual(
      scenarios.default!.versions,
    );
  });

  it("rejects an unknown scenario and lists the known ones", () => {
    expect(() => createFixtureStudio("?scenario=nope")).toThrow(
      'Unknown scenario "nope". Known scenarios: default.',
    );
  });

  it("does not treat inherited object keys as scenarios", () => {
    expect(() => createFixtureStudio("?scenario=toString")).toThrow(
      /Unknown scenario/,
    );
  });

  it("gives each adapter its own frozen copy of the scenario data", () => {
    const api = createFixtureStudio("");
    expect(Object.isFrozen(api.versions)).toBe(true);
    expect(api.versions).not.toBe(scenarios.default!.versions);
  });
});
