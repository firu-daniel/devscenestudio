// Shape of the API the preload exposes on `window.studio`. Keep in step with src/preload/preload.ts.
interface StudioVersions {
  readonly electron: string;
  readonly chrome: string;
  readonly node: string;
}

interface StudioApi {
  readonly versions: StudioVersions;
}

interface Window {
  readonly studio: StudioApi;
}
