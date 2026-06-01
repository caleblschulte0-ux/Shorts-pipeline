# One-click TikTok demo runner for Windows.
#
# To use: right-click this file → Run with PowerShell.
# If Windows blocks it, paste into PowerShell:
#   Set-ExecutionPolicy -Scope Process Bypass; .\tiktok_demo_oneclick.ps1
#
# It will: check Python, install requests if needed, prompt for the
# client secret on first run (saved locally), download a sample video
# if none exists, then run the OAuth + upload demo.

$ErrorActionPreference = "Stop"

# --- 1. Make sure Python is on PATH ---------------------------------
$py = (Get-Command python -ErrorAction SilentlyContinue) `
    ?? (Get-Command py     -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Host "Python not found. Opening the python.org installer page." `
        -ForegroundColor Yellow
    Start-Process "https://www.python.org/downloads/"
    Read-Host "Install Python (check 'Add to PATH'), then press Enter to continue"
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw "Still no python — re-open PowerShell after installing." }
}
Write-Host "[+] Python: $($py.Source)"

# --- 2. requests dep ------------------------------------------------
& $py.Source -c "import requests" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[+] installing requests..."
    & $py.Source -m pip install --quiet requests
}

# --- 3. Client key + secret. Key is public, secret is from dashboard
$env:TIKTOK_CLIENT_KEY = "aw9hmk3x2xmhv4mv"
$secretFile = "$PSScriptRoot\.tiktok_secret"
if (Test-Path $secretFile) {
    $env:TIKTOK_CLIENT_SECRET = (Get-Content $secretFile).Trim()
} else {
    Write-Host ""
    Write-Host "Paste your TikTok Client Secret from the developer dashboard:" `
        -ForegroundColor Cyan
    $sec = Read-Host -AsSecureString
    $env:TIKTOK_CLIENT_SECRET = [System.Net.NetworkCredential]::new("", $sec).Password
    Set-Content -Path $secretFile -Value $env:TIKTOK_CLIENT_SECRET -NoNewline
    Write-Host "[+] secret saved locally (gitignored)"
}

# --- 4. Find a video to upload --------------------------------------
$videoPath = Get-ChildItem -Path "$PSScriptRoot\output" -Filter "*.mp4" `
    -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $videoPath) {
    Write-Host "[+] no mp4 in output/ — downloading a 5MB sample to use..."
    $sample = "$PSScriptRoot\sample.mp4"
    Invoke-WebRequest `
        -Uri "https://download.samplelib.com/mp4/sample-5s.mp4" `
        -OutFile $sample
    $videoPath = Get-Item $sample
}
Write-Host "[+] uploading: $($videoPath.FullName)"

# --- 5. Go ----------------------------------------------------------
Write-Host ""
Write-Host "=== Start your screen recording NOW (Win+G) ===" `
    -ForegroundColor Green
Read-Host "Press Enter when recording is rolling"

& $py.Source "$PSScriptRoot\tiktok_demo.py" $videoPath.FullName
