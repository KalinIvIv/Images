@echo off
echo ========================================
echo Image Auto-Cropper - Building EXE
echo ========================================
echo.

echo Checking if PyInstaller is installed...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
) else (
    echo PyInstaller is already installed.
    echo.
)

echo Building executable...
echo This may take a few minutes...
echo.

pyinstaller --onefile --noconsole --name "ImageAutoCropper" --icon=NONE --hidden-import=pillow_avif auto_crop.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo The executable has been created in the 'dist' folder:
echo   %~dp0dist\ImageAutoCropper.exe
echo.
echo You can now double-click ImageAutoCropper.exe to run the program.
echo.
pause
