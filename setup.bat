@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ensure-env.bat" test
if errorlevel 1 goto setup_failed
echo.
echo [SETUP] Complete. Run run-app.bat to start or run-tests.bat to test.
if /i not "%~1"=="/quiet" pause
endlocal & exit /b 0

:setup_failed
echo.
echo [ERROR] Setup was not completed. See the messages above.
if /i not "%~1"=="/quiet" pause
endlocal & exit /b 1
