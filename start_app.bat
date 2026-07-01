@echo off
setlocal
cd /d "%~dp0"

set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PY_EXE=venv\Scripts\python.exe"
)

if not defined PY_EXE (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY_EXE=py"
        set "PY_ARGS=-3"
    ) else (
        where python >nul 2>nul
        if not errorlevel 1 (
            set "PY_EXE=python"
        ) else (
            echo Python not found. Please install Python and try again.
            pause
            exit /b 1
        )
    )
)

if /I "%PY_EXE%"=="py" (
    start "" /min %PY_EXE% %PY_ARGS% app.py
) else (
    start "" /min "%PY_EXE%" app.py
)

ping 127.0.0.1 -n 4 >nul
start "" http://127.0.0.1:5000

exit /b 0
