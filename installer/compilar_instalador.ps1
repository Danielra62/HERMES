$ErrorActionPreference = "Stop"

$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = (Get-Command python -ErrorAction Stop).Source
$pyinstaller = (Get-Command pyinstaller -ErrorAction Stop).Source
$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
}
if (-not $iscc) {
    throw "No se encontró ISCC.exe de Inno Setup 6."
}

$version = [regex]::Match(
    (Get-Content (Join-Path $raiz "shared\constants.py") -Raw),
    '(?m)^VERSION\s*=\s*"([^"]+)"'
).Groups[1].Value
if (-not $version) {
    throw "No se pudo leer VERSION desde shared\constants.py."
}

$deps = Join-Path $env:TEMP "hermes-client-build-deps-$([guid]::NewGuid().ToString('N'))"
$pythonPathOriginal = $env:PYTHONPATH
$null = New-Item -ItemType Directory -Force -Path $deps
Push-Location $raiz
try {
    & $python -m pip install --disable-pip-version-check --no-warn-script-location --upgrade --target $deps -r cliente\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron preparar las dependencias del cliente." }

    $env:PYTHONPATH = "$deps;$raiz"
    & $python -c "import PIL; assert PIL.__version__ == '11.3.0', PIL.__version__; print('Pillow de compilacion:', PIL.__version__)"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo seleccionar la versión de Pillow definida por el cliente." }

    & $pyinstaller --clean --noconfirm --onedir --noconsole --name HermesCliente `
        --paths $raiz --paths $deps --distpath dist --workpath build\pyinstaller-cliente `
        cliente\main.py
    if ($LASTEXITCODE -ne 0) { throw "Falló la compilación de HermesCliente.exe." }

    $null = New-Item -ItemType Directory -Force -Path dist\instalador
    & $pyinstaller --clean --noconfirm --onefile --noconsole --name HermesRegistro `
        --distpath dist --workpath build\pyinstaller-registro installer\registrar_inventario.py
    if ($LASTEXITCODE -ne 0) { throw "Falló la compilación de HermesRegistro.exe." }

    & $iscc "/DAppVersion=$version" installer\HermesCliente.iss
    if ($LASTEXITCODE -ne 0) { throw "Falló la creación del instalador Inno Setup." }
}
finally {
    $env:PYTHONPATH = $pythonPathOriginal
    Pop-Location
    if (Test-Path $deps) {
        Remove-Item -LiteralPath $deps -Recurse -Force
    }
}

Write-Host "Instalador creado en dist\instalador\HERMES-Cliente-Setup-$version.exe"
