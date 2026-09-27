@echo off
REM ============================================================
REM  LYRA INSTALLER (run once)
REM ============================================================
cd /d %~dp0

echo.
echo [1/4] Checking Python...
python --version >nul 2>nul
if errorlevel 1 (
    echo Python is not installed. Install it from https://python.org
    echo and tick "Add Python to PATH" during setup.
    pause
    exit /b 1
)

echo.
echo [2/4] Creating virtual environment...
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo.
echo [3/4] Installing packages...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo Package installation failed. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo [4/4] Downloading Lyra's voice pack...
python -m lyra.setup_voice

echo.
echo Checking Ollama...
where ollama >nul 2>nul
if errorlevel 1 (
    echo.
    echo [!] Ollama was not found.
    echo     1. Install it from https://ollama.com
    echo     2. Then run:  ollama pull phi4-mini:3.8b
) else (
    ollama list 2>nul | findstr /c:"phi4-mini" >nul
    if errorlevel 1 (
        echo Pulling the Lyra brain model ^(one time, ~2.5 GB^)...
        ollama pull phi4-mini:3.8b
    )
)

echo.
echo ============================================================
echo  Install complete! Start Lyra with run_lyra.bat
echo ============================================================
pause
