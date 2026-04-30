@echo off
title Smart Study AI Assistant
color 0A

echo.
echo  ==========================================
echo    SMART STUDY AI ASSISTANT - LAUNCHER
echo  ==========================================
echo.

REM --- Activate virtual environment if it exists ---
IF EXIST "venv\Scripts\activate.bat" (
    echo [1/3] Activating virtual environment...
    call venv\Scripts\activate.bat
) ELSE (
    echo [!] No virtual environment found. Run setup.bat first!
    pause
    exit /b
)

REM --- Check .env file ---
IF NOT EXIST ".env" (
    echo [!] WARNING: .env file not found. AI features may not work.
    echo     Create a .env file with your GROQ_API_KEY.
    pause
)

REM --- Launch Flask App ---
echo [2/3] Starting Flask backend...
echo [3/3] Open your browser at: http://127.0.0.1:5000
echo.
echo  Press CTRL+C to stop the server.
echo  ==========================================
echo.

cd backend
python app.py

pause
