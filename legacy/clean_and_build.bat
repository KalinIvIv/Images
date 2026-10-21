@echo off
echo ========================================
echo Cleaning old build files...
echo ========================================

if exist dist (
    echo Removing dist folder...
    rmdir /s /q dist
)

if exist build (
    echo Removing build folder...
    rmdir /s /q build
)

if exist ImageAutoCropper.spec (
    echo Removing spec file...
    del ImageAutoCropper.spec
)

if exist __pycache__ (
    echo Removing __pycache__ folder...
    rmdir /s /q __pycache__
)

echo.
echo Cleanup complete!
echo.
echo ========================================
echo Building EXE...
echo ========================================
echo.

pyinstaller --onefile --noconsole --name "ImageAutoCropper" --hidden-import=pillow_avif auto_crop.py

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
echo The executable has been created:
echo   %~dp0dist\ImageAutoCropper.exe
echo.
pause
