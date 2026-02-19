# kanjilens.ps1 - Long-running hotkey listener for kanjilens OCR
# Press Ctrl+Shift+Z to snip a region and OCR it.
# Results appear in a floating overlay that auto-dismisses after 5 seconds.
# Press Ctrl+C to stop.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# P/Invoke signatures for global hotkey registration and message loop
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class HotKeyHelper {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    [DllImport("user32.dll")]
    public static extern bool PeekMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax, uint wRemoveMsg);

    [StructLayout(LayoutKind.Sequential)]
    public struct MSG {
        public IntPtr hwnd;
        public uint message;
        public IntPtr wParam;
        public IntPtr lParam;
        public uint time;
        public POINT pt;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int x;
        public int y;
    }

    public const int WM_HOTKEY = 0x0312;
    public const uint MOD_CONTROL = 0x0002;
    public const uint MOD_SHIFT = 0x0004;
    public const uint VK_Z = 0x5A;
}
"@

$HOTKEY_ID = 1

# TODO: overlay disabled for now, revisit later
# $overlayScript = Join-Path $env:TEMP "kanjilens-overlay.ps1"

function Invoke-KanjiLens {
    # Clear the clipboard so we can detect when a new image arrives
    [System.Windows.Forms.Clipboard]::Clear()

    # Send Win+Shift+S to open Snipping Tool via explorer shell URI
    Start-Process "ms-screenclip:"

    # Poll clipboard for an image (timeout after 30 seconds)
    $deadline = (Get-Date).AddSeconds(30)
    $img = $null
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 300
        try {
            $img = [System.Windows.Forms.Clipboard]::GetImage()
        } catch {
            $img = $null
        }
        if ($null -ne $img) { break }
    }

    if ($null -eq $img) {
        Write-Host "No snip captured (timed out or cancelled)." -ForegroundColor Yellow
        return
    }

    # Save to temp PNG
    $tmp = [System.IO.Path]::Combine(
        [System.IO.Path]::GetTempPath(),
        "kanjilens_" + [System.IO.Path]::GetRandomFileName() + ".png"
    )
    $img.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)
    $img.Dispose()

    try {
        # Force UTF-8 so Japanese text survives the WSL-to-PowerShell boundary
        $prevEncoding = [Console]::OutputEncoding
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

        $wslPath = wsl wslpath -a $tmp.Replace('\', '\\')
        # Talk directly to the OCR server over Unix socket for minimal latency
        $result = wsl python3 -c "
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/tmp/kanjilens.sock')
s.sendall(sys.argv[1].encode())
s.shutdown(socket.SHUT_WR)
d = b''
while c := s.recv(4096): d += c
sys.stdout.buffer.write(d)
" "$wslPath"
        $text = ($result | Out-String).Trim()

        [Console]::OutputEncoding = $prevEncoding

        if ([string]::IsNullOrWhiteSpace($text)) {
            Write-Host "OCR returned no text." -ForegroundColor Yellow
            return
        }

        Write-Host $text
        [System.Windows.Forms.Clipboard]::SetText($text)
    }
    finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

# --- Start OCR server if not already running ---

$socketPath = "/tmp/kanjilens.sock"
# Check if a server is actually responding, not just if the socket file exists
$healthCheck = @'
import socket
try:
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    s.connect("/tmp/kanjilens.sock")
    s.close()
    print("yes")
except:
    print("no")
'@
$serverRunning = ($healthCheck | wsl python3)
if ($serverRunning -ne "yes") {
    # Clean up stale socket
    wsl rm -f $socketPath 2>$null
    Write-Host "Starting OCR server (loading model)..." -ForegroundColor Cyan
    $serverLog = Join-Path $env:TEMP "kanjilens-server.log"
    $wslLog = "/tmp/kanjilens-server.log"
    Start-Process wsl -WindowStyle Hidden -ArgumentList 'bash', '-c', "cd ~/projects/kanjilens && source .venv/bin/activate && kanjilens serve > $wslLog 2>&1"
    # Wait for the socket to appear
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 1000
        $ready = wsl bash -c "test -S $socketPath && echo yes"
        if ($ready -eq "yes") { break }
    }
    if ($ready -ne "yes") {
        Write-Host "OCR server failed to start. Log:" -ForegroundColor Red
        wsl cat $wslLog 2>$null
        exit 1
    }
    Write-Host "OCR server ready. Log: $wslLog (in WSL)" -ForegroundColor Cyan
} else {
    Write-Host "OCR server already running." -ForegroundColor Cyan
}

# --- Main ---

$registered = [HotKeyHelper]::RegisterHotKey(
    [IntPtr]::Zero,
    $HOTKEY_ID,
    [HotKeyHelper]::MOD_CONTROL -bor [HotKeyHelper]::MOD_SHIFT,
    [HotKeyHelper]::VK_Z
)

if (-not $registered) {
    Write-Host "Failed to register hotkey Ctrl+Shift+Z. Is another instance running?" -ForegroundColor Red
    exit 1
}

Write-Host "kanjilens is running. Press Ctrl+Shift+Z to snip and OCR." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop."

try {
    $msg = New-Object HotKeyHelper+MSG
    while ($true) {
        # Check for hotkey messages without blocking
        while ([HotKeyHelper]::PeekMessage(
            [ref]$msg,
            [IntPtr]::Zero,
            [HotKeyHelper]::WM_HOTKEY,
            [HotKeyHelper]::WM_HOTKEY,
            1  # PM_REMOVE
        )) {
            if ($msg.message -eq [HotKeyHelper]::WM_HOTKEY) {
                Invoke-KanjiLens
            }
        }
        Start-Sleep -Milliseconds 100
    }
}
finally {
    [HotKeyHelper]::UnregisterHotKey([IntPtr]::Zero, $HOTKEY_ID) | Out-Null
    # Stop the OCR server we started
    wsl bash -c "rm -f /tmp/kanjilens.sock; pkill -f 'kanjilens serve'" 2>$null
    Write-Host "`nHotkey unregistered. Goodbye." -ForegroundColor Green
}
