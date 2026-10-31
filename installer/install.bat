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

REM Chrome may still have the previous version running; Windows will not replace a running program.
tasklist /fi "imagename eq PhotoCut.exe" 2>nul | find /i "PhotoCut.exe" >nul
if not errorlevel 1 (
    echo Closing the PhotoCut helper that Chrome is still running...
    taskkill /im PhotoCut.exe /f >nul 2>&1
    ping -n 3 127.0.0.1 >nul
)

if exist "%DEST%\app" rmdir /s /q "%DEST%\app"
if exist "%DEST%\app" goto :locked
xcopy /e /i /q /y "%~dp0app" "%DEST%\app" >nul || goto :copyfail
xcopy /e /i /q /y "%~dp0extension" "%DEST%\extension" >nul || goto :copyfail

"%DEST%\app\PhotoCut.exe" install || goto :regfail

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

:locked
echo.
echo INSTALL FAILED - the old PhotoCut files are still in use.
echo Close all Chrome windows (and Chrome in the system tray: right-click, Exit),
echo or end "PhotoCut" in Task Manager (Ctrl+Shift+Esc), then run install.bat again.
pause
exit /b 1

:copyfail
echo.
echo INSTALL FAILED - could not copy the files to %DEST%
echo Check that the disk is not full and that no PhotoCut window or folder is open, then try again.
pause
exit /b 1

:regfail
echo.
echo INSTALL FAILED - the files were copied, but registering PhotoCut with Chrome did not work.
echo If antivirus blocked PhotoCut.exe, allow it and run install.bat again.
pause
exit /b 1
