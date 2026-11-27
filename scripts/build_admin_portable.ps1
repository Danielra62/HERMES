$ErrorActionPreference = "Stop"

$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$salida = Join-Path $desktop "HermesAdmin-portable"
$python = (Get-Command python -ErrorAction Stop).Source
$pyinstaller = (Get-Command pyinstaller -ErrorAction Stop).Source
$pythonVenv = Join-Path $raiz "venv\Scripts\python.exe"
$venvSitePackages = Join-Path $raiz "venv\Lib\site-packages"
$baseTemporal = Join-Path $env:TEMP "HermesAdminPortable-$([guid]::NewGuid().ToString('N'))"
$dist = Join-Path $baseTemporal "dist"
$work = Join-Path $baseTemporal "work"
$specs = Join-Path $baseTemporal "spec"
$icon = Join-Path $baseTemporal "HermesAdmin.ico"
$pythonPathOriginal = $env:PYTHONPATH

$actualizarExistente = Test-Path -LiteralPath $salida
if ($actualizarExistente) {
    foreach ($requerido in @(
        (Join-Path $salida "HermesAdmin.exe"),
        (Join-Path $salida "data\hermes.db"),
        (Join-Path $salida "_internal")
    )) {
        if (-not (Test-Path -LiteralPath $requerido)) {
            throw "La carpeta existe pero no parece un paquete portable Hermes: $requerido"
        }
    }

    $ejecutableExistente = Join-Path $salida "HermesAdmin.exe"
    $procesoActivo = Get-CimInstance Win32_Process -Filter "Name='HermesAdmin.exe'" |
        Where-Object { $_.ExecutablePath -eq $ejecutableExistente }
    if ($procesoActivo) {
        throw "Cierra Hermes Admin portable antes de actualizarlo: $ejecutableExistente"
    }
}
if (-not (Test-Path -LiteralPath $pythonVenv)) {
    throw "No se encontró el Python del entorno del proyecto: $pythonVenv"
}
if (-not (Test-Path -LiteralPath (Join-Path $raiz "hermes.db"))) {
    throw "No se encontró hermes.db en la raíz del proyecto."
}

$null = New-Item -ItemType Directory -Force -Path $baseTemporal
$pythonIcono = @'
import sys
from PIL import Image, ImageDraw

destino = sys.argv[1]
imagen = Image.new("RGBA", (256, 256), (22, 38, 68, 255))
dibujo = ImageDraw.Draw(imagen)
dibujo.rounded_rectangle((12, 12, 244, 244), radius=48, fill=(22, 38, 68, 255), outline=(58, 160, 220, 255), width=10)
dibujo.rectangle((64, 58, 96, 198), fill=(245, 249, 255, 255))
dibujo.rectangle((160, 58, 192, 198), fill=(245, 249, 255, 255))
dibujo.rectangle((96, 112, 160, 144), fill=(58, 190, 150, 255))
imagen.save(destino, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
'@

try {
    $pythonIcono | & $pythonVenv - $icon
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo generar el icono del administrador."
    }

    $env:PYTHONPATH = "$raiz;$venvSitePackages"
    Push-Location $raiz
    try {
        $argumentos = @(
            "--clean",
            "--noconfirm",
            "--onedir",
            "--console",
            "--name", "HermesAdmin",
            "--icon", $icon,
            "--paths", $raiz,
            "--paths", $venvSitePackages,
            "--specpath", $specs,
            "--add-data", "$raiz\admin\ui;admin\ui",
            "--distpath", $dist,
            "--workpath", $work
        )
        foreach ($moduloOpcional in @(
            "IPython",
            "jedi",
            "matplotlib",
            "nbformat",
            "numpy",
            "parso",
            "tkinter",
            "zmq"
        )) {
            $argumentos += @("--exclude-module", $moduloOpcional)
        }
        $argumentos += "scripts\admin_portable_entry.py"
        & $pyinstaller @argumentos
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller no pudo compilar el administrador."
        }
    }
    finally {
        Pop-Location
    }

    $paqueteTemporal = Join-Path $dist "HermesAdmin"
    $datos = Join-Path $paqueteTemporal "data"
    $almacenamiento = Join-Path $datos "storage"
    $fuentes = Join-Path $paqueteTemporal "source"
    $null = New-Item -ItemType Directory -Force -Path $almacenamiento
    $null = New-Item -ItemType Directory -Force -Path $fuentes

    $dbOrigen = Join-Path $raiz "hermes.db"
    $dbDestino = Join-Path $datos "hermes.db"
    $copiarBd = @'
import sqlite3
import sys

origen = sqlite3.connect(sys.argv[1])
destino = sqlite3.connect(sys.argv[2])
try:
    origen.backup(destino)
finally:
    destino.close()
    origen.close()
'@
    $copiarBd | & $pythonVenv - $dbOrigen $dbDestino
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear la copia segura de hermes.db."
    }

    $validarBd = @'
import sqlite3
import sys

conexion = sqlite3.connect(sys.argv[1])
try:
    integridad = conexion.execute("PRAGMA integrity_check").fetchone()[0]
    claves = conexion.execute("PRAGMA foreign_key_check").fetchall()
    grupos = conexion.execute("SELECT COUNT(*) FROM grupos").fetchone()[0]
    clientes = conexion.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    if integridad != "ok" or claves:
        raise SystemExit(f"Base no válida: integrity={integridad}, foreign_keys={claves}")
    print(f"hermes.db validada: {grupos} grupos, {clientes} clientes")
finally:
    conexion.close()
'@
    $validarBd | & $pythonVenv - $dbDestino
    if ($LASTEXITCODE -ne 0) {
        throw "La copia de hermes.db no pasó la validación."
    }

    $almacenamientoOrigen = Join-Path $raiz "admin\storage"
    if (Test-Path -LiteralPath $almacenamientoOrigen) {
        Get-ChildItem -LiteralPath $almacenamientoOrigen -File -Recurse |
            ForEach-Object {
                $relativa = $_.FullName.Substring($almacenamientoOrigen.Length).TrimStart("\")
                $destinoArchivo = Join-Path $almacenamiento $relativa
                $directorioDestino = Split-Path -Parent $destinoArchivo
                $null = New-Item -ItemType Directory -Force -Path $directorioDestino
                Copy-Item -LiteralPath $_.FullName -Destination $destinoArchivo
            }
    }

    $extensionesFuente = @(".py", ".html", ".css", ".js")
    foreach ($arbol in @("admin", "shared", "scripts")) {
        $origenArbol = Join-Path $raiz $arbol
        Get-ChildItem -LiteralPath $origenArbol -File -Recurse |
            Where-Object {
                $_.Extension.ToLowerInvariant() -in $extensionesFuente -and
                $_.FullName -notmatch "\\__pycache__\\"
            } |
            ForEach-Object {
                $relativa = $_.FullName.Substring($raiz.Length).TrimStart("\")
                $destinoArchivo = Join-Path $fuentes $relativa
                $directorioDestino = Split-Path -Parent $destinoArchivo
                $null = New-Item -ItemType Directory -Force -Path $directorioDestino
                Copy-Item -LiteralPath $_.FullName -Destination $destinoArchivo
            }
    }
    Copy-Item -LiteralPath (Join-Path $raiz "README.md") -Destination $fuentes

    $inventario = Join-Path $desktop "inventario_hermes.json"
    if (
        (Test-Path -LiteralPath $inventario) -and
        -not (Test-Path -LiteralPath (Join-Path $paqueteTemporal "inventario_hermes.json"))
    ) {
        Copy-Item -LiteralPath $inventario -Destination $paqueteTemporal
    }

    $readmePaquete = @'
HERMES ADMIN — CARPETA PORTABLE

Ejecuta "Iniciar Hermes Admin.lnk". El acceso directo inicia la consola
minimizada y abre el navegador predeterminado cuando Flask responde.
Si el navegador no se abre, visita http://127.0.0.1:8080.

Esta carpeta usa exclusivamente la base SQLite de data\hermes.db y guarda
las imágenes en data\storage. No necesita Python instalado para ejecutarse.
No muevas el ejecutable fuera de esta carpeta; puedes mover toda la carpeta.

Puertos usados:
- TCP 8080: interfaz web/API del administrador.
- TCP 5006: heartbeats recibidos de los clientes.
- TCP 5005: órdenes salientes hacia los clientes.

La copia inicial de hermes.db conserva sus grupos y clientes actuales, incluidos
los registros de prueba CRUD. inventario_hermes.json, si está presente, es solo
una copia de referencia: esta versión no lo importa automáticamente.

El código fuente de admin, shared y scripts está en source\. No se copiaron
credenciales ni el archivo .env del entorno de desarrollo.
'@
    Set-Content -LiteralPath (Join-Path $paqueteTemporal "LEEME.txt") `
        -Value $readmePaquete -Encoding UTF8

    $null = New-Item -ItemType Directory -Force -Path $desktop
    if ($actualizarExistente) {
        Remove-Item -LiteralPath (Join-Path $salida "_internal") -Recurse -Force
        Move-Item -LiteralPath (Join-Path $paqueteTemporal "_internal") `
            -Destination $salida
        Copy-Item -LiteralPath (Join-Path $paqueteTemporal "HermesAdmin.exe") `
            -Destination (Join-Path $salida "HermesAdmin.exe") -Force

        $fuentesExistentes = Join-Path $salida "source"
        if (Test-Path -LiteralPath $fuentesExistentes) {
            Remove-Item -LiteralPath $fuentesExistentes -Recurse -Force
        }
        Move-Item -LiteralPath (Join-Path $paqueteTemporal "source") `
            -Destination $salida
        Copy-Item -LiteralPath (Join-Path $paqueteTemporal "LEEME.txt") `
            -Destination (Join-Path $salida "LEEME.txt") -Force
        if (-not (Test-Path -LiteralPath (Join-Path $salida "inventario_hermes.json"))) {
            $inventarioTemporal = Join-Path $paqueteTemporal "inventario_hermes.json"
            if (Test-Path -LiteralPath $inventarioTemporal) {
                Copy-Item -LiteralPath $inventarioTemporal -Destination $salida
            }
        }
    }
    else {
        Move-Item -LiteralPath $paqueteTemporal -Destination $salida
    }

    $ejecutable = Join-Path $salida "HermesAdmin.exe"
    $iconoFinal = Join-Path $salida "HermesAdmin.ico"
    Copy-Item -LiteralPath $icon -Destination $iconoFinal -Force
    $atajo = Join-Path $salida "Iniciar Hermes Admin.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $enlace = $shell.CreateShortcut($atajo)
    $enlace.TargetPath = $ejecutable
    $enlace.WorkingDirectory = $salida
    $enlace.IconLocation = "$iconoFinal,0"
    $enlace.WindowStyle = 7
    $enlace.Description = "Inicia el administrador web HERMES"
    $enlace.Save()

    if ($actualizarExistente) {
        Write-Host "Administrador portable actualizado; los datos se conservaron: $salida"
    }
    else {
        Write-Host "Administrador portable creado en: $salida"
    }
    Write-Host "Acceso web: http://127.0.0.1:8080"
}
finally {
    $env:PYTHONPATH = $pythonPathOriginal
    if (Test-Path -LiteralPath $baseTemporal) {
        Remove-Item -LiteralPath $baseTemporal -Recurse -Force
    }
}
