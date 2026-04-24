@echo off
chcp 65001 >nul
echo ================================================
echo   YouTube MP3 Extractor — Build Executável
echo ================================================
echo.

:: Check PyInstaller
.venv\Scripts\pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller no venv...
    .venv\Scripts\pip install pyinstaller -q
)

echo Construindo executável...
echo.

.venv\Scripts\pyinstaller ^
    --name "YouTube MP3 Extractor" ^
    --onedir ^
    --windowed ^
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
    echo [ERRO] Falha ao construir o executável.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Build concluído!
echo   Executável em: dist\YouTube MP3 Extractor\
echo ================================================
echo.
echo Para distribuir: compacte a pasta dist\YouTube MP3 Extractor\
echo.
pause
