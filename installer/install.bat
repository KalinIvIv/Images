@echo off
REM Installs PhotoCut for the current Windows user (no admin rights needed).
setlocal
set "DEST=%LOCALAPPDATA%\PhotoCut"

echo Installing PhotoCut to %DEST% ...
if exist "%DEST%\app" rmdir /s /q "%DEST%\app"
xcopy /e /i /q /y "%~dp0app" "%DEST%\app" >nul || goto :fail
xcopy /e /i /q /y "%~dp0extension" "%DEST%\extension" >nul || goto :fail

"%DEST%\app\PhotoCut.exe" install || goto :fail

echo.
echo ============================================================
echo  PhotoCut app installed. Now add the extension to Chrome:
echo.
echo  1. In Chrome, open  chrome://extensions
echo  2. Turn on "Developer mode" (top right)
echo  3. Click "Load unpacked" and choose this folder:
echo        %DEST%\extension
echo  4. Pin PhotoCut (puzzle icon), then open its Options
echo     to set your output folder and the shared rules file.
echo.
echo  Updating? Click the reload arrow on PhotoCut in chrome://extensions.
echo ============================================================
explorer "%DEST%"
pause
exit /b 0

:fail
echo.
echo INSTALL FAILED - make sure Chrome is not saving images right now and try again.
pause
exit /b 1
