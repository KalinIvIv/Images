@echo off
echo ========================================
echo Packaging for Distribution
echo ========================================
echo.

if not exist dist\ImageAutoCropper.exe (
    echo ERROR: ImageAutoCropper.exe not found in dist folder!
    echo Please run clean_and_build.bat first to create the EXE.
    pause
    exit /b 1
)

echo Creating distribution folder...
if exist ImageAutoCropper_Distribution (
    rmdir /s /q ImageAutoCropper_Distribution
)
mkdir ImageAutoCropper_Distribution

echo Copying files...
copy dist\ImageAutoCropper.exe ImageAutoCropper_Distribution\
copy INSTRUCTIONS_FOR_USERS.txt ImageAutoCropper_Distribution\
copy config.json.example ImageAutoCropper_Distribution\

echo.
echo ========================================
echo Package Ready!
echo ========================================
echo.
echo Files in ImageAutoCropper_Distribution folder:
dir /b ImageAutoCropper_Distribution
echo.
echo To distribute to colleagues:
echo 1. Compress ImageAutoCropper_Distribution folder to ZIP
echo 2. Send the ZIP file
echo 3. Tell them to extract and run ImageAutoCropper.exe
echo.
pause
