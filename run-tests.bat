@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ensure-env.bat" test
if errorlevel 1 goto startup_failed

echo.
echo [TESTS] Running AI Market Research Agent tests...
".venv\Scripts\python.exe" -m pytest -q
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" echo [ERROR] Some tests failed with code %EXITCODE%.
echo.
pause
endlocal & exit /b %EXITCODE%

:startup_failed
echo.
echo [ERROR] Automatic Python setup failed. See details above.
pause
endlocal & exit /b 1
