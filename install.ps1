# BaixaTrack - Instalador PowerShell
# Uso: irm https://raw.githubusercontent.com/bdsromulo/BaixaTrack/main/install.ps1 | iex

$GITHUB_REPO = "bdsromulo/BaixaTrack"

# ──────────────────────────────────────────────────────────────────────────────
$INSTALL_DIR = "$env:LOCALAPPDATA\BaixaTrack"
$DESKTOP_LINK = "$env:USERPROFILE\Desktop\BaixaTrack.lnk"
$RELEASE_API = "https://api.github.com/repos/$GITHUB_REPO/releases/latest"

$ProgressPreference = 'SilentlyContinue'  # faster downloads

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  BaixaTrack - Instalador"                        -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Try to install from latest GitHub Release ──────────────────────────────
# Prefer the dedicated installer (.exe). Fall back to the zipped portable build.
$installed = $false
try {
    Write-Host "Verificando releases no GitHub..." -ForegroundColor Gray
    $release = Invoke-RestMethod -Uri $RELEASE_API `
        -Headers @{ Accept = 'application/vnd.github.v3+json'; 'User-Agent' = 'BaixaTrack-Installer' } `
        -ErrorAction Stop

    # ── 1a. Prefer the Inno Setup installer (.exe) ────────────────────────────
    $setupAsset = $release.assets | Where-Object { $_.name -like "*Setup*.exe" } | Select-Object -First 1
    if ($setupAsset) {
        Write-Host "Baixando instalador $($release.tag_name)..." -ForegroundColor Green
        $setupPath = "$env:TEMP\BaixaTrack-Setup.exe"
        Invoke-WebRequest -Uri $setupAsset.browser_download_url -OutFile $setupPath

        Write-Host "Iniciando assistente de instalacao..." -ForegroundColor Green
        Write-Host ""
        Write-Host "Siga as instrucoes na janela do instalador para escolher pasta," -ForegroundColor Yellow
        Write-Host "criar atalho e executar o app ao terminar." -ForegroundColor Yellow
        Write-Host ""
        # Run interactively so user can pick install dir, shortcut, run-after.
        Start-Process -FilePath $setupPath -Wait
        Remove-Item $setupPath -Force -ErrorAction SilentlyContinue
        $installed = $true
    }
    else {
        # ── 1b. Fallback: extract portable zip and create our own shortcut ────
        $zipAsset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
        if ($zipAsset) {
            Write-Host "Baixando versao portable $($release.tag_name)..." -ForegroundColor Green

            $zipPath = "$env:TEMP\BaixaTrack_setup.zip"
            Invoke-WebRequest -Uri $zipAsset.browser_download_url -OutFile $zipPath

            Write-Host "Extraindo para $INSTALL_DIR ..."
            New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
            Expand-Archive -Path $zipPath -DestinationPath $INSTALL_DIR -Force
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

            $exeFile = Get-ChildItem -Path $INSTALL_DIR -Recurse -Filter "BaixaTrack.exe" |
                Select-Object -First 1

            if ($exeFile) {
                $shell = New-Object -ComObject WScript.Shell
                $shortcut = $shell.CreateShortcut($DESKTOP_LINK)
                $shortcut.TargetPath = $exeFile.FullName
                $shortcut.WorkingDirectory = $exeFile.DirectoryName
                $shortcut.IconLocation = "$($exeFile.FullName),0"
                $shortcut.Save()

                Write-Host ""
                Write-Host "Instalado com sucesso!" -ForegroundColor Green
                Write-Host "Atalho criado na area de trabalho." -ForegroundColor Green
                Write-Host ""
                Write-Host "Na primeira execucao o FFmpeg sera baixado automaticamente (~170 MB)." -ForegroundColor Yellow
                Write-Host ""

                Start-Process $exeFile.FullName
                $installed = $true
            }
        }
    }
}
catch {
    Write-Host "Nenhuma release encontrada. Instalando via Python..." -ForegroundColor Yellow
}

if ($installed) { exit 0 }

# ── 2. Fallback: Python-based install ─────────────────────────────────────────
Write-Host ""
Write-Host "Instalando versao Python do app..." -ForegroundColor Cyan
Write-Host ""

# Check / install Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Python nao encontrado. Instalando via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "[ERRO] Nao foi possivel instalar o Python. Instale manualmente em https://python.org" -ForegroundColor Red
        exit 1
    }
}

# Download repo zip
Write-Host "Baixando repositorio..."
$repoZip = "$env:TEMP\baixatrack_repo.zip"
$repoUrl = "https://github.com/$GITHUB_REPO/archive/refs/heads/main.zip"
Invoke-WebRequest -Uri $repoUrl -OutFile $repoZip

$extractTo = "$env:TEMP\baixatrack_extract"
Remove-Item $extractTo -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $repoZip -DestinationPath $extractTo -Force
Remove-Item $repoZip -Force -ErrorAction SilentlyContinue

# Move to install dir
$repoFolder = Get-ChildItem -Path $extractTo -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
Copy-Item -Path "$($repoFolder.FullName)\*" -Destination $INSTALL_DIR -Recurse -Force
Remove-Item $extractTo -Recurse -Force -ErrorAction SilentlyContinue

# Create venv and install deps
Write-Host "Criando ambiente virtual e instalando dependencias..."
Set-Location $INSTALL_DIR
python -m venv .venv
& ".venv\Scripts\pip" install -r requirements.txt -q

# Download FFmpeg via setup_ffmpeg.py (if present) — otherwise app handles it on first launch
if (Test-Path "$INSTALL_DIR\setup_ffmpeg.py") {
    Write-Host "Baixando FFmpeg (~170 MB)..."
    & ".venv\Scripts\python" setup_ffmpeg.py
}

# Desktop shortcut: launch pythonw.exe directly so no console window appears.
$pythonwExe = Join-Path $INSTALL_DIR ".venv\Scripts\pythonw.exe"
$iconPath = Join-Path $INSTALL_DIR "assets\logo.ico"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($DESKTOP_LINK)
$shortcut.TargetPath = $pythonwExe
$shortcut.Arguments = "`"$INSTALL_DIR\app.py`""
$shortcut.WorkingDirectory = $INSTALL_DIR
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()

Write-Host ""
Write-Host "Instalado com sucesso!" -ForegroundColor Green
Write-Host "Atalho criado na area de trabalho." -ForegroundColor Green
Write-Host ""

# Launch without a console window
Start-Process -FilePath $pythonwExe -ArgumentList "`"$INSTALL_DIR\app.py`"" -WorkingDirectory $INSTALL_DIR
