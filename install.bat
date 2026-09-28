@echo off
setlocal EnableExtensions
set "SOURCE=%~dp0"
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\LYRA"
set "PYTHON="

echo.
echo LYRA installer - application files will be installed to:
echo   %INSTALL_DIR%
echo Personal settings, memory and logs remain in %APPDATA%\Lyra.
echo.

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
robocopy "%SOURCE%" "%INSTALL_DIR%" /E /NFL /NDL /NJH /NJS /NP /XD .git .venv venv models data logs __pycache__ .pytest_cache /XF memory.json *.pyc
if errorlevel 8 (
  echo Could not copy LYRA application files.
  pause
  exit /b 1
)
if exist "%SOURCE%memory.json" if not exist "%APPDATA%\Lyra\memory.json" (
  if not exist "%APPDATA%\Lyra" mkdir "%APPDATA%\Lyra"
  copy /Y "%SOURCE%memory.json" "%APPDATA%\Lyra\memory.json" >nul
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 --version >nul 2>nul
  if not errorlevel 1 set "PYTHON=py -3.12"
  if not defined PYTHON (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON=py -3.11"
  )
  if not defined PYTHON (
    py -3.10 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON=py -3.10"
  )
)
if not defined PYTHON (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
  echo Python 3.10-3.12 is required to install LYRA.
  echo Install Python from https://www.python.org/downloads/ and run install.bat again.
  pause
  exit /b 1
)

echo Creating LYRA's private Python environment...
%PYTHON% -m venv "%INSTALL_DIR%\.venv"
if errorlevel 1 goto :failed

echo Installing application dependencies. This may take several minutes...
"%INSTALL_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip
"%INSTALL_DIR%\.venv\Scripts\python.exe" -m pip install -r "%INSTALL_DIR%\requirements.txt"
if errorlevel 1 goto :failed

powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALL_DIR%\launcher\create_shortcut.ps1" -InstallDir "%INSTALL_DIR%"
if errorlevel 1 echo Could not create shortcuts. You can still launch with run_lyra.bat.

echo.
echo LYRA application installed. Ollama and the Phi model are managed separately.
echo Double-click the LYRA desktop shortcut; it will check Ollama and ask before downloading the model.
echo.
pause
exit /b 0

:failed
echo Installation failed. Fix the dependency error and run install.bat again.
pause
exit /b 1
