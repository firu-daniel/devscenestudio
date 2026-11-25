import { contextBridge } from "electron";

// The renderer gets named, read-only capabilities only: never ipcRenderer or Node APIs.
const studioApi = {
  versions: Object.freeze({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  }),
};

contextBridge.exposeInMainWorld("studio", studioApi);
