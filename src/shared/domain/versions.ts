// Runtime versions the preload reports. Day 1 replaces this hello-world surface with StudioApi.
export interface RuntimeVersions {
  readonly electron: string;
  readonly chrome: string;
  readonly node: string;
}

export function describeVersions(versions: RuntimeVersions): string {
  return `Electron ${versions.electron} · Chromium ${versions.chrome} · Node ${versions.node}`;
}
