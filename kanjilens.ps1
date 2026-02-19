# kanjilens.ps1 - Long-running hotkey listener for kanjilens OCR
# Press Ctrl+Shift+K to snip a region and OCR it.
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
    public const uint VK_K = 0x4B;
}
"@

$HOTKEY_ID = 1

function Show-Overlay {
    param([string]$Text)

    # Spawn a separate PowerShell process for the overlay so it gets its own
    # message loop, avoiding conflicts with our hotkey PeekMessage loop.
    $escapedText = $Text -replace '"', '\"' -replace "'", "''"
    Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', @"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

`$font = New-Object System.Drawing.Font('Meiryo UI', 18)
`$bmp = New-Object System.Drawing.Bitmap(1, 1)
`$g = [System.Drawing.Graphics]::FromImage(`$bmp)
`$sz = `$g.MeasureString('$escapedText', `$font, (New-Object System.Drawing.SizeF(760, 0)))
`$g.Dispose(); `$bmp.Dispose()

`$pad = 24
`$w = [int](`$sz.Width + `$pad * 2 + 2)
`$h = [int](`$sz.Height + `$pad * 2 + 2)

`$form = New-Object System.Windows.Forms.Form
`$form.FormBorderStyle = 'None'
`$form.StartPosition = 'Manual'
`$form.TopMost = `$true
`$form.ShowInTaskbar = `$false
`$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
`$form.Opacity = 0.92
`$form.ClientSize = New-Object System.Drawing.Size(`$w, `$h)

`$label = New-Object System.Windows.Forms.Label
`$label.Text = '$escapedText'
`$label.ForeColor = [System.Drawing.Color]::White
`$label.Font = `$font
`$label.Location = New-Object System.Drawing.Point(`$pad, `$pad)
`$label.Size = New-Object System.Drawing.Size((`$w - `$pad * 2), (`$h - `$pad * 2))
`$form.Controls.Add(`$label)

`$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
`$form.Location = New-Object System.Drawing.Point((`$screen.Right - `$w - 20), (`$screen.Bottom - `$h - 20))

`$form.Add_Click({ `$form.Close() })
`$label.Add_Click({ `$form.Close() })

`$timer = New-Object System.Windows.Forms.Timer
`$timer.Interval = 5000
`$timer.Add_Tick({ `$form.Close() })
`$timer.Start()

[System.Windows.Forms.Application]::Run(`$form)
"@
}

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
        $result = wsl bash -c "cd ~/projects/kanjilens && source .venv/bin/activate && kanjilens '$wslPath'" 2>&1
        $text = ($result | Out-String).Trim()

        [Console]::OutputEncoding = $prevEncoding

        if ([string]::IsNullOrWhiteSpace($text)) {
            Write-Host "OCR returned no text." -ForegroundColor Yellow
            return
        }

        Write-Host "OCR: $text"
        Show-Overlay -Text $text
    }
    finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

# --- Main ---

$registered = [HotKeyHelper]::RegisterHotKey(
    [IntPtr]::Zero,
    $HOTKEY_ID,
    [HotKeyHelper]::MOD_CONTROL -bor [HotKeyHelper]::MOD_SHIFT,
    [HotKeyHelper]::VK_K
)

if (-not $registered) {
    Write-Host "Failed to register hotkey Ctrl+Shift+K. Is another instance running?" -ForegroundColor Red
    exit 1
}

Write-Host "kanjilens is running. Press Ctrl+Shift+K to snip and OCR." -ForegroundColor Green
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
    Write-Host "`nHotkey unregistered. Goodbye." -ForegroundColor Green
}
