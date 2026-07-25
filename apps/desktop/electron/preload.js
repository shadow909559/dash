import { contextBridge } from "electron";
contextBridge.exposeInMainWorld("dash", {
    version: "0.1.0",
    platform: process.platform,
});
