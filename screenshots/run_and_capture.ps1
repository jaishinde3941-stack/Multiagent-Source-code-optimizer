# Focus the browser showing the app
Add-Type -Name WH3 -Namespace N3 -MemberDefinition @"
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(System.IntPtr hWnd);
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
"@

$procs = Get-Process | Where-Object {
    $_.MainWindowTitle -like "*CompilerAI*" -or
    $_.MainWindowTitle -like "*localhost*" -or
    $_.MainWindowTitle -like "*Optimization*"
}

if ($procs.Count -gt 0) {
    $hwnd = $procs[0].MainWindowHandle
    [N3.WH3]::ShowWindow($hwnd, 3)
    [N3.WH3]::SetForegroundWindow($hwnd)
    Write-Host "Focused: $($procs[0].MainWindowTitle)"
} else {
    Start-Process "chrome" "--new-window --start-maximized http://localhost:5173"
    Start-Sleep 4
}
Start-Sleep -Milliseconds 1200

function Take-Screenshot($filename) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $b = New-Object System.Drawing.Bitmap($s.Width, $s.Height)
    $g = [System.Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($s.Location, [System.Drawing.Point]::Empty, $s.Size)
    $b.Save($filename, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $b.Dispose()
    Write-Host "Saved: $filename"
}

Take-Screenshot "E:\SEM 4\CD_Refined\screenshots\01_idle.png"
Write-Host "Idle screenshot taken."
