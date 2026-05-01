@echo off
chcp 65001 >nul
echo ================================================
echo   BaixaTrack - Build Executavel + Instalador
echo ================================================
echo.

:: Check PyInstaller
.venv\Scripts\pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller no venv...
    .venv\Scripts\pip install pyinstaller -q
)

:: Ensure logo.ico exists (regenerate from PNG if missing).
:: NOTE: cannot use an `if (...)` block here because Python tuple syntax
:: like (16,16),(32,32) confuses the CMD parser. Goto-label instead.
if exist "assets\logo.ico" goto :icon_ready
echo Gerando assets\logo.ico a partir de assets\logo.png...
.venv\Scripts\python -c "from PIL import Image; Image.open('assets/logo.png').save('assets/logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if errorlevel 1 (
    echo [ERRO] Falha ao gerar o icone.
    pause
    exit /b 1
)
:icon_ready

echo Construindo executavel...
echo.

.venv\Scripts\pyinstaller ^
    --name "BaixaTrack" ^
    --onedir ^
    --windowed ^
    --icon "assets\logo.ico" ^
    --add-data "assets\logo.ico;assets" ^
    --add-data "assets\logo.png;assets" ^
    --collect-all customtkinter ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import PIL._imagingtk ^
    --hidden-import yt_dlp ^
    --hidden-import downloader ^
    --hidden-import ffmpeg_manager ^
    --noconfirm ^
    app.py

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao construir o executavel.
    pause
    exit /b 1
)

echo.
echo Executavel pronto em: dist\BaixaTrack\
echo.

:: ── Tentar compilar o instalador com Inno Setup ─────────────────────────────
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo ================================================
    echo   Build concluido SEM instalador.
    echo ================================================
    echo.
    echo Inno Setup nao encontrado. Para gerar o instalador .exe:
    echo   winget install JRSoftware.InnoSetup
    echo e depois rode build.bat novamente.
    echo.
    echo Para distribuir agora: compacte a pasta dist\BaixaTrack\
    pause
    exit /b 0
)

echo Compilando instalador com Inno Setup...
"%ISCC%" installer.iss
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao compilar o instalador.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Build + Instalador concluidos!
echo ================================================
echo.
echo - Pasta do app:    dist\BaixaTrack\
echo - Instalador:      dist\BaixaTrack-Setup.exe
echo.
pause
