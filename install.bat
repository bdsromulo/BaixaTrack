@echo off
chcp 65001 >nul
echo ================================================
echo   YouTube MP3 Extractor - Instalação
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python não encontrado!
    echo Instale o Python 3.8+ em: https://www.python.org/downloads/
    echo Marque a opção "Add Python to PATH" durante a instalação.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [AVISO] FFmpeg não encontrado.
    echo O FFmpeg é necessário para converter áudio para MP3.
    echo.
    echo Baixe em: https://ffmpeg.org/download.html
    echo   - Escolha "Windows builds by BtbN" ou "gyan.dev"
    echo   - Extraia e adicione a pasta "bin" ao PATH do sistema
    echo   - OU instale via winget: winget install ffmpeg
    echo.
    set /p CONTINUE="Continuar mesmo assim? (s/n): "
    if /i not "%CONTINUE%"=="s" exit /b 1
) else (
    echo [OK] FFmpeg encontrado.
)
echo.

:: Create virtual environment
if not exist ".venv" (
    echo Criando ambiente virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
) else (
    echo [OK] Ambiente virtual já existe.
)
echo.

:: Install dependencies
echo Instalando dependências...
call .venv\Scripts\pip install --upgrade pip -q
call .venv\Scripts\pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependências.
    pause
    exit /b 1
)
echo [OK] Dependências instaladas.
echo.

:: Create run.bat
echo Criando atalho de execução...
(
    echo @echo off
    echo cd /d "%~dp0"
    echo .venv\Scripts\python app.py
) > run.bat
echo [OK] Atalho "run.bat" criado.
echo.

echo ================================================
echo   Instalação concluída com sucesso!
echo   Execute "run.bat" para iniciar o aplicativo.
echo ================================================
echo.
pause
