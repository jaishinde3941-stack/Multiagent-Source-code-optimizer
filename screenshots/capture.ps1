Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Find Chrome window with localhost in title
$procs = Get-Process | Where-Object { $_.MainWindowTitle -like "*localhost*" -or $_.MainWindowTitle -like "*Compiler*" -or $_.MainWindowTitle -like "*5173*" }

if ($procs.Count -eq 0) {
    # Open Chrome with the app URL
    Start-Process "chrome" "--new-window --start-maximized http://localhost:5173"
    Start-Sleep -Seconds 4
    $procs = Get-Process | Where-Object { $_.MainWindowTitle -like "*localhost*" -or $_.MainWindowTitle -like "*Compiler*" }
}

if ($procs.Count -gt 0) {
    Add-Type -Name WinHelper -Namespace Native -MemberDefinition @"
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(System.IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
"@
    $hwnd = $procs[0].MainWindowHandle
    [Native.WinHelper]::ShowWindow($hwnd, 3)   # SW_MAXIMIZE
    [Native.WinHelper]::SetForegroundWindow($hwnd)
    Write-Host "Focused: $($procs[0].MainWindowTitle)"
}

Start-Sleep -Milliseconds 1800

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$g   = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bmp.Save("E:\SEM 4\CD_Refined\screenshots\app_live.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Host "Screenshot saved."
