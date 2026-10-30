@echo off
REM Installs PhotoCut for the current Windows user (no admin rights needed).
setlocal
set "DEST=%LOCALAPPDATA%\PhotoCut"

if not exist "%~dp0app\PhotoCut.exe" (
    echo.
    echo Cannot find app\PhotoCut.exe next to this install.bat:
    echo     %~dp0
    echo.
    echo  - If you opened install.bat from inside PhotoCut.zip, close this window,
    echo    right-click PhotoCut.zip, choose "Extract All...", then run install.bat
    echo    from the extracted folder.
    echo  - Do not run the install.bat in the source code's "installer" folder;
    echo    use the one from release\PhotoCut.zip made by build.bat.
    pause
    exit /b 1
)

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
