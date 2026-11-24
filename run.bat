@echo off
REM Launch the PDF Sign & Fill editor.
REM Creates a local virtualenv on first run, then starts the app.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Setting up virtual environment...
    python -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :fail
)

".venv\Scripts\python.exe" app.py %*
goto :eof

:fail
echo.
echo Setup failed. Install Python 3.10+ from https://python.org and run this again.
pause
