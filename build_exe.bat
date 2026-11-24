@echo off
REM Build a standalone Windows executable:  dist\PDF Sign and Fill.exe
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :fail
)

echo Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install --quiet pyinstaller || goto :fail

echo Building...
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm tools\pdfsign.spec || goto :fail

echo.
echo Done:  dist\PDF Sign and Fill.exe
echo Verify with:  .venv\Scripts\python tools\verify_exe.py
goto :eof

:fail
echo.
echo Build failed. Check the messages above.
pause
