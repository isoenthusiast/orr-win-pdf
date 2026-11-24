@echo off
REM Launch the PDF Sign & Fill editor.
REM Creates a local virtualenv on first run, then starts the app.
setlocal
cd /d "%~dp0"

REM ---- find a usable Python 3.11+ ------------------------------------
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY goto :no_python
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 goto :old_python

REM ---- first run: build the virtualenv -------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Setting up the virtual environment for the first time.
    echo This needs a one-time internet connection.
    %PY% -m venv .venv || goto :venv_failed
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :pip_failed
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :pip_failed
)

".venv\Scripts\python.exe" app.py %*
if errorlevel 1 goto :app_failed
goto :eof

:no_python
echo.
echo Python 3.11 or newer is needed, and it was not found on this PC.
echo.
echo   1. Download the installer from  https://www.python.org/downloads/
echo   2. Tick "Add python.exe to PATH" while installing
echo   3. Run this file again
echo.
pause
exit /b 1

:old_python
echo.
echo The Python on this PC is too old - version 3.11 or newer is needed.
echo Install a newer one from https://www.python.org/downloads/
echo.
pause
exit /b 1

:venv_failed
echo.
echo Could not create the virtual environment.
echo Reinstall Python and tick "tcl/tk and IDLE" - the interface needs Tk.
echo.
pause
exit /b 1

:pip_failed
echo.
echo Could not download the packages.
echo The first run needs an internet connection.
echo If this PC is behind a proxy, set PIP_INDEX_URL and try again.
echo.
pause
exit /b 1

:app_failed
echo.
echo The app stopped with an error above.
echo A report may have been written to:
echo   %%APPDATA%%\PDF Sign and Fill\error.log
echo.
pause
exit /b 1
