@echo off
title Smart Study AI - First Time Setup
color 0B

echo.
echo  ==========================================
echo    SMART STUDY AI - FIRST TIME SETUP
echo  ==========================================
echo.

REM --- Check Python ---
echo [1/4] Checking Python installation...
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found! Please install Python 3.10+ from https://python.org
    pause
    exit /b
)
python --version

REM --- Create virtual environment ---
echo.
echo [2/4] Creating virtual environment...
IF NOT EXIST "venv" (
    python -m venv venv
    echo Virtual environment created!
) ELSE (
    echo Virtual environment already exists. Skipping...
)

REM --- Activate and install dependencies ---
echo.
echo [3/4] Installing dependencies from requirements.txt...
call venv\Scripts\activate.bat
pip install -r requirements.txt

REM --- Check .env ---
echo.
echo [4/4] Checking .env file...
IF NOT EXIST ".env" (
    echo [!] .env file not found! Creating a template...
    (
        echo GROQ_API_KEY=your_groq_api_key_here
        echo SECRET_KEY=super_secret_study_key
        echo DATABASE_URL=
    ) > .env
    echo.
    echo  ==========================================
    echo  [ACTION REQUIRED] Open the .env file and
    echo  replace 'your_groq_api_key_here' with your
    echo  actual Groq API key from https://console.groq.com
    echo  ==========================================
) ELSE (
    echo .env file found!
)

echo.
echo  ==========================================
echo   Setup Complete! Run 'run.bat' to start.
echo  ==========================================
echo.
pause
