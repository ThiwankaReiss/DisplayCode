import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  platform: process.platform,
  version: process.version,
  closeWindow: () => ipcRenderer.invoke('close-window')
})
