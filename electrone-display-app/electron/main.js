import { app, BrowserWindow, Menu, ipcMain } from 'electron'
import isDev from 'electron-is-dev'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 480,
    frame: false,
    fullscreen: true,
    kiosk: true,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    fullscreenable: true,
    show: false
  })

  const startUrl = isDev
    ? 'http://localhost:5173'
    : `file://${path.join(__dirname, '../dist/index.html')}`

  mainWindow.loadURL(startUrl)

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // Uncomment the line below to open DevTools in development
  // if (isDev) {
  //   mainWindow.webContents.openDevTools()
  // }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// Remove application menu
Menu.setApplicationMenu(null)

// Handle close window IPC
ipcMain.handle('close-window', () => {
  if (mainWindow) {
    mainWindow.close()
  }
  app.quit()
  return true
})

app.on('ready', createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
