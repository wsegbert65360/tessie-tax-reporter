@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Tesla Tax Reporter: Environment Setup
echo ========================================

if not exist .venv (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment. 
        echo Please ensure Python is installed and in your PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment already exists.
)

echo [2/3] Activating environment and checking dependencies...
call .venv\Scripts\activate

:: Checking for fpdf2 as a marker of updated requirements
pip show fpdf2 >nul 2>&1
if errorlevel 1 (
    echo Missing dependencies found. Installing...
    pip install -r requirements.txt
) else (
    echo All dependencies are up to date.
)

echo [3/3] Launching Application...
python gui.py

if errorlevel 1 (
    echo.
    echo Application exited with an error. 
    echo Check debug.log for details.
    pause
)

endlocal
