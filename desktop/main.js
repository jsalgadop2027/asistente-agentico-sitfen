// SITFEN Desktop — proceso principal de Electron (cliente ligero).
// Sirve el frontend local (renderer/) por HTTP en 127.0.0.1 para que los ES
// modules + importmap funcionen (file:// los bloquea por CORS). El chat y el TTS
// se consumen del backend en Cloud Run vía API_BASE definido en el renderer.
const { app, BrowserWindow, session } = require('electron');
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, 'renderer');
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.mjs':  'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.glb':  'model/gltf-binary',
  '.png':  'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.svg':  'image/svg+xml', '.ico': 'image/x-icon',
  '.wasm': 'application/wasm', '.map': 'application/json',
  '.woff': 'font/woff', '.woff2': 'font/woff2'
};

function startServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      let urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      if (urlPath === '/') urlPath = '/index.html';
      const filePath = path.join(ROOT, path.normalize(urlPath));
      if (!filePath.startsWith(ROOT)) { res.writeHead(403); res.end('Forbidden'); return; }
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end('Not found'); return; }
        const ext = path.extname(filePath).toLowerCase();
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
  });
}

async function createWindow() {
  const port = await startServer();

  // Permitir micrófono (entrada de voz).
  session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) => {
    cb(permission === 'media' || permission === 'microphone');
  });

  const win = new BrowserWindow({
    width: 1120, height: 740, minWidth: 900, minHeight: 600,
    title: 'SITFEN — Asistente conversacional de Información Temprana',
    backgroundColor: '#0e1726',
    webPreferences: { contextIsolation: true, nodeIntegration: false }
  });
  win.removeMenu();
  win.loadURL(`http://127.0.0.1:${port}/index.html`);
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
