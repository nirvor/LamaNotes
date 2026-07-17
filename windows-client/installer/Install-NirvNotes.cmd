@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-NirvNotes.ps1" %*
pause
