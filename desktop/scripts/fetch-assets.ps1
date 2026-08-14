# Descarga y empaqueta localmente los assets del avatar (three.js, TalkingHead,
# módulos de lip-sync y el modelo .glb) en desktop/renderer/, para que la app de
# escritorio funcione sin depender de CDNs externos en runtime.
# Uso:  powershell -ExecutionPolicy Bypass -File desktop\scripts\fetch-assets.ps1
$ErrorActionPreference = "Stop"
$Root  = Split-Path -Parent $PSScriptRoot          # .../desktop
$rend  = Join-Path $Root "renderer"
$three = Join-Path $rend "vendor\three"
$th    = Join-Path $rend "vendor\talkinghead"
New-Item -ItemType Directory -Force -Path $three, $th | Out-Null

$THREE_VER = "0.170.0"
$TH_VER    = "1.4"
$tmp = Join-Path $env:TEMP ("three_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

Write-Host "Descargando three.js $THREE_VER ..." -ForegroundColor Cyan
Invoke-WebRequest "https://registry.npmjs.org/three/-/three-$THREE_VER.tgz" -OutFile "$tmp\three.tgz"
tar -xzf "$tmp\three.tgz" -C $tmp
if (Test-Path "$three\build")        { Remove-Item "$three\build" -Recurse -Force }
if (Test-Path "$three\examples\jsm") { Remove-Item "$three\examples\jsm" -Recurse -Force }
Copy-Item "$tmp\package\build" "$three\build" -Recurse -Force
New-Item -ItemType Directory -Force -Path "$three\examples" | Out-Null
Copy-Item "$tmp\package\examples\jsm" "$three\examples\jsm" -Recurse -Force

Write-Host "Descargando TalkingHead $TH_VER + lip-sync ..." -ForegroundColor Cyan
$base = "https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@$TH_VER/modules"
foreach ($f in @("talkinghead.mjs","dynamicbones.mjs","lipsync-fi.mjs","lipsync-en.mjs","lipsync-lt.mjs")) {
  Invoke-WebRequest "$base/$f" -OutFile (Join-Path $th $f)
}

Write-Host "Descargando modelo brunette.glb (animador Mujer) ..." -ForegroundColor Cyan
Invoke-WebRequest "https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@$TH_VER/avatars/brunette.glb" -OutFile (Join-Path $rend "avatar.glb")

# Animador "Hombre" del selector (ver renderer/index.html, MODEL_URLS.M).
# Opcional: sin MALE_AVATAR_URL definido, esa opción del selector simplemente
# no estará disponible (switchAvatar falla-abierto y avisa en pantalla).
if ($env:MALE_AVATAR_URL) {
  Write-Host "Descargando modelo masculino (avatar_male.glb) ..." -ForegroundColor Cyan
  try {
    Invoke-WebRequest $env:MALE_AVATAR_URL -OutFile (Join-Path $rend "avatar_male.glb")
  } catch {
    Write-Host "No se pudo descargar MALE_AVATAR_URL: $_" -ForegroundColor Yellow
  }
} else {
  Write-Host "MALE_AVATAR_URL no definido: se omite el animador 'Hombre'." -ForegroundColor Yellow
}

# Animador "Robot" del selector (ver renderer/index.html, MODEL_URLS.R): visor
# Three.js propio, sin lipsync (no es un avatar Ready Player Me). Mismo asset
# que el Dockerfile del agente: "Animated Robot" de Quaternius (CC0), vía el
# CDN estático de poly.pizza.
Write-Host "Descargando modelo avatar_robot.glb (animador Robot) ..." -ForegroundColor Cyan
try {
  Invoke-WebRequest "https://static.poly.pizza/7d95dbce-8c73-489b-8298-f430b1f0dbdf.glb" -OutFile (Join-Path $rend "avatar_robot.glb")
} catch {
  Write-Host "No se pudo descargar el modelo del robot: $_" -ForegroundColor Yellow
}

Remove-Item $tmp -Recurse -Force
Write-Host "Assets listos en $rend" -ForegroundColor Green