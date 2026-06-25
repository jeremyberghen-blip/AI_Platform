@echo off
title AI Harness Launcher

echo Starting AI Harness...

:: Kill anything already on port 8080
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Start harness module in its own window
start "AI Harness - Module" cmd /k "cd /d "C:\AI Harness Project\harness_module" && .\venv\Scripts\activate && python main.py"

:: Give the module a moment to start
timeout /t 3 /nobreak >nul

:: Start frontend dev server in its own window
start "AI Harness - Frontend" cmd /k "cd /d "C:\AI Harness Project\frontend" && npm run dev"

:: Give the frontend a moment to start
timeout /t 4 /nobreak >nul

:: Open in browser
start http://localhost:1420

echo Done. Close this window.
timeout /t 2 /nobreak >nul
exit
