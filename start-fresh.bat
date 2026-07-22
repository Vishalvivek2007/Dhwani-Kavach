@echo off
REM ── Dhwani-Kavach FRESH launcher (Windows) ────────────────────────────────
REM Kills anything already listening on 8000/8080 (stale backend/frontend from
REM a previous run — the usual cause of stale routes / port-already-in-use),
REM then starts both fresh and opens the dashboard.
cd /d "%~dp0"

echo Killing anything on ports 8000 and 8080 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1

REM Prefer the project venv (pinned deps: torch, onnxruntime, librosa, ...).
REM Bare "python" is often a different interpreter missing these.
set "PYEXE=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"

echo Starting backend on http://localhost:8000 (using %PYEXE%) ...
start "Dhwani Backend" cmd /k ""%PYEXE%" -m uvicorn app.main:app --app-dir backend --port 8000 --reload"

echo Starting frontend on http://localhost:8080 ...
start "Dhwani Frontend" cmd /k "cd frontend && npm run dev"

echo Waiting for servers to come up...
timeout /t 14 /nobreak >nul

start "" http://localhost:8080
echo.
echo Demo is up:
echo   Frontend    http://localhost:8080
echo   Backend     http://localhost:8000
echo   Cases       http://localhost:8000/cases
echo   Campaigns   http://localhost:8000/campaigns
echo   Governance  http://localhost:8000/governance
echo   Metrics     http://localhost:8000/metrics
echo.
echo Close the two opened windows to stop the demo.
