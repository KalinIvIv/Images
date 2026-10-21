@echo off
REM Build PhotoCut and package it for colleagues: creates release\PhotoCut.zip
setlocal
cd /d "%~dp0.."

echo Installing build dependencies...
python -m pip install -r requirements.txt || goto :fail

echo Running tests...
python -m pytest -q || goto :fail

echo Building PhotoCut.exe...
python -m PyInstaller --noconfirm --clean --onedir --console --name PhotoCut --paths app ^
  --distpath build\dist --workpath build\work --specpath build app\PhotoCut.py || goto :fail

echo Packaging...
if exist release rmdir /s /q release
mkdir release\PhotoCut
xcopy /e /i /q /y build\dist\PhotoCut release\PhotoCut\app >nul
xcopy /e /i /q /y extension release\PhotoCut\extension >nul
copy /y installer\install.bat release\PhotoCut\ >nul
copy /y installer\uninstall.bat release\PhotoCut\ >nul
copy /y docs\HOW_TO_USE.md release\PhotoCut\ >nul
copy /y docs\popup.png release\PhotoCut\ >nul
powershell -NoProfile -Command "Compress-Archive -Path release\PhotoCut -DestinationPath release\PhotoCut.zip -Force" || goto :fail

echo.
echo Done: release\PhotoCut.zip
echo Send it to colleagues: unzip, double-click install.bat, follow HOW_TO_USE.md
pause
exit /b 0

:fail
echo.
echo BUILD FAILED
pause
exit /b 1
