@echo off
REM Removes PhotoCut (your saved images and the shared rules file are not touched).
setlocal
set "DEST=%LOCALAPPDATA%\PhotoCut"
if exist "%DEST%\app\PhotoCut.exe" "%DEST%\app\PhotoCut.exe" uninstall
if exist "%DEST%" rmdir /s /q "%DEST%"
echo PhotoCut removed. Also click "Remove" on PhotoCut in chrome://extensions.
pause
