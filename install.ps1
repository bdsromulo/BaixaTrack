# YouTube MP3 Extractor - Instalador PowerShell
# Uso: irm https://raw.githubusercontent.com/bdsromulo/BaixaTrack/main/install.ps1 | iex

$GITHUB_REPO = "bdsromulo/BaixaTrack"

# ──────────────────────────────────────────────────────────────────────────────
$INSTALL_DIR = "$env:LOCALAPPDATA\YouTubeMP3Extractor"
$DESKTOP_LINK = "$env:USERPROFILE\Desktop\YouTube MP3 Extractor.lnk"
$RELEASE_API = "https://api.github.com/repos/$GITHUB_REPO/releases/latest"

$ProgressPreference = 'SilentlyContinue'  # faster downloads

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  YouTube MP3 Extractor - Instalador"           -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Try to install from latest GitHub Release (exe) ────────────────────────
$exeInstalled = $false
try {
    Write-Host "Verificando releases no GitHub..." -ForegroundColor Gray
    $release = Invoke-RestMethod -Uri $RELEASE_API `
        -Headers @{ Accept = 'application/vnd.github.v3+json'; 'User-Agent' = 'YTExtractor-Installer' } `
        -ErrorAction Stop

    $asset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1

    if ($asset) {
        Write-Host "Baixando versao $($release.tag_name)..." -ForegroundColor Green

        $zipPath = "$env:TEMP\YouTubeMP3Extractor_setup.zip"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath

        Write-Host "Extraindo para $INSTALL_DIR ..."
        New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
        Expand-Archive -Path $zipPath -DestinationPath $INSTALL_DIR -Force
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

        # Find the exe
        $exeFile = Get-ChildItem -Path $INSTALL_DIR -Recurse -Filter "YouTube MP3 Extractor.exe" |
        Select-Object -First 1

        if ($exeFile) {
            # Desktop shortcut
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut($DESKTOP_LINK)
            $shortcut.TargetPath = $exeFile.FullName
            $shortcut.WorkingDirectory = $exeFile.DirectoryName
            $shortcut.Save()

            Write-Host ""
            Write-Host "Instalado com sucesso!" -ForegroundColor Green
            Write-Host "Atalho criado na area de trabalho." -ForegroundColor Green
            Write-Host ""
            Write-Host "Na primeira execucao o FFmpeg sera baixado automaticamente (~170 MB)." -ForegroundColor Yellow
            Write-Host ""

            Start-Process $exeFile.FullName
            $exeInstalled = $true
        }
    }
}
catch {
    Write-Host "Nenhuma release encontrada. Instalando via Python..." -ForegroundColor Yellow
}

if ($exeInstalled) { exit 0 }

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
$repoZip = "$env:TEMP\ytmp3_repo.zip"
$repoUrl = "https://github.com/$GITHUB_REPO/archive/refs/heads/main.zip"
Invoke-WebRequest -Uri $repoUrl -OutFile $repoZip

$extractTo = "$env:TEMP\ytmp3_extract"
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

# Download FFmpeg via setup_ffmpeg.py
Write-Host "Baixando FFmpeg (~170 MB)..."
& ".venv\Scripts\python" setup_ffmpeg.py

# Create run.bat
@"
@echo off
cd /d "$INSTALL_DIR"
.venv\Scripts\python app.py
"@ | Set-Content "$INSTALL_DIR\run.bat" -Encoding ASCII

# Desktop shortcut pointing to run.bat (hidden window)
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($DESKTOP_LINK)
$shortcut.TargetPath = "cmd.exe"
$shortcut.Arguments = "/c `"$INSTALL_DIR\run.bat`""
$shortcut.WorkingDirectory = $INSTALL_DIR
$shortcut.WindowStyle = 7  # Minimized (hides the console)
$shortcut.Save()

Write-Host ""
Write-Host "Instalado com sucesso!" -ForegroundColor Green
Write-Host "Atalho criado na area de trabalho." -ForegroundColor Green
Write-Host ""

& cmd /c "$INSTALL_DIR\run.bat"
