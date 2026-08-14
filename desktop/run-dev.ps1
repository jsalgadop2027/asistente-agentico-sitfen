# Lanzador de desarrollo de SITFEN Desktop.
# Limpia ELECTRON_RUN_AS_NODE (si el entorno lo trae, Electron correría como Node
# y fallaría), instala dependencias si faltan y abre la app.
# Uso:  powershell -ExecutionPolicy Bypass -File desktop\run-dev.ps1
$ErrorActionPreference = "Stop"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
Set-Location $PSScriptRoot

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Host "No se encontró Node.js/npm en el PATH. Instálalo desde https://nodejs.org" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path "renderer\vendor\three\build\three.module.js")) {
  Write-Host "Descargando assets del avatar..." -ForegroundColor Cyan
  powershell -ExecutionPolicy Bypass -File "scripts\fetch-assets.ps1"
}
if (-not (Test-Path "node_modules\electron\dist\electron.exe")) {
  Write-Host "Instalando Electron (primera vez)..." -ForegroundColor Cyan
  cmd /c "npm install"
}
Write-Host "Abriendo SITFEN Desktop..." -ForegroundColor Green
cmd /c "npm start"
