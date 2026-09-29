@echo off
setlocal
set "LYRA_HOME=%~dp0"
cd /d "%LYRA_HOME%"
if not exist "%LYRA_HOME%.venv\Scripts\python.exe" (
  echo LYRA is not installed yet. Run install.bat first.
  pause
  exit /b 1
)
"%LYRA_HOME%.venv\Scripts\python.exe" -m lyra.launcher %*
if errorlevel 1 pause
