@echo off
setlocal

set "REPO_ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\run-offline.ps1"

endlocal
