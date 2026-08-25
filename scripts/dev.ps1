# RecoverAI Development Orchestrator
# Starts backend and frontend development servers

$toolsDir = "C:\Users\sdgg7\.tools"
$env:PATH = "$toolsDir\nodejs;$toolsDir\git\cmd;$toolsDir\git\bin;C:\Users\sdgg7\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none;C:\Users\sdgg7\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Scripts;$env:PATH"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  RecoverAI — Track 3: AI Revenue Recovery" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if backend venv exists
if (!(Test-Path "backend\.venv")) {
    Write-Host "Creating Python virtual environment in backend/.venv..." -ForegroundColor Yellow
    uv venv backend\.venv --python 3.11
    & "backend\.venv\Scripts\pip.exe" install -r backend\requirements.txt
}

# Check if frontend node_modules exists
if (!(Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    cd frontend
    npm install
    cd ..
}

Write-Host "Starting Backend on http://127.0.0.1:8000..." -ForegroundColor Green
Start-Process -FilePath "backend\.venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app --reload --port 8000" -WorkingDirectory "backend"

Write-Host "Starting Frontend on http://localhost:5173..." -ForegroundColor Green
Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory "frontend"

Write-Host "`nServers launched in background!" -ForegroundColor Cyan
Write-Host "Backend Health: http://127.0.0.1:8000/health"
Write-Host "Frontend App:   http://localhost:5173"
