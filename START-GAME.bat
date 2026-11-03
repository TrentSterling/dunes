@echo off
title Dunes Server
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Node.js is not installed. Download the LTS version from https://nodejs.org
  echo  install it, then double-click START-GAME.bat again.
  echo.
  start https://nodejs.org/en/download
  pause
  exit /b
)
if not exist "node_modules\ws\" (
  echo Installing the game server package (one time only^)...
  call npm install --no-audit --no-fund
)
start "" http://localhost:5189
node server.js 5189
pause
