@echo off
REM ============================================================
REM  LYRA LAUNCHER
REM ============================================================
cd /d %~dp0
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python main.py %*
pause
