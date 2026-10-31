@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0run-app.bat"
set "EXITCODE=%ERRORLEVEL%"
endlocal & exit /b %EXITCODE%
