import { contextBridge } from "electron";
import type { StudioApi } from "../shared/contract/studio-api";

// The renderer gets named, read-only capabilities only: never ipcRenderer or Node APIs.
const studioApi = {
  versions: Object.freeze({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  }),
} satisfies StudioApi;

contextBridge.exposeInMainWorld("studio", studioApi);
