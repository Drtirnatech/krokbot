@echo off
REM Windows CMD script to create and set up the KrokBot virtual environment

echo ============================================================
echo   KrokBot Virtual Environment Setup (.venv)
echo ============================================================

IF NOT EXIST ".venv" (
    echo [1/3] Creating Python virtual environment (.venv)...
    python -m venv .venv
) ELSE (
    echo [1/3] Virtual environment (.venv) already exists.
)

echo [2/3] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/3] Upgrading pip and installing requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ============================================================
echo   KrokBot Virtual Environment Setup Complete!
echo   To activate in CMD, run:   .venv\Scripts\activate.bat
echo   To start KrokBot, run:     python -m krokbot.main
echo ============================================================
pause
