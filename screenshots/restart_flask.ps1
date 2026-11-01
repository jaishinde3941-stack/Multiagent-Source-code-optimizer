# Kill all python processes running app.py
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*app.py*" -or $_.MainWindowTitle -like "*app.py*"
} | Stop-Process -Force

# Also kill anything on port 5000
$conn = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($conn) {
    $procId = ($conn | Select-Object -ExpandProperty OwningProcess -Unique)
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Write-Host "Killed process $procId on port 5000"
}

Start-Sleep -Seconds 1

# Start fresh
Set-Location "E:\SEM 4\CD_Refined"
Start-Process -FilePath "python" -ArgumentList "app.py" -WindowStyle Hidden
Write-Host "Flask restarted with updated timeout=360 and warmup logic"
