# One-click TikTok demo runner for Windows PowerShell 5.1+ / 7+.
#
# Use: right-click this file -> Run with PowerShell.
# If Windows blocks it, paste into PowerShell:
#   Set-ExecutionPolicy -Scope Process Bypass -Force; .\tiktok_demo_oneclick.ps1
#
# It checks Python, installs requests, prompts for the client secret
# the first time, finds a video to upload, then runs the OAuth +
# upload demo. Pure ASCII + PowerShell 5.1 compatible (no ?? operator
# or smart quotes).

$ErrorActionPreference = "Stop"

# --- 1. Find Python ------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "Python not found. Opening the python.org installer page." -ForegroundColor Yellow
    Start-Process "https://www.python.org/downloads/"
    Read-Host "Install Python (check 'Add Python to PATH'), then press Enter"
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) {
        throw "Still no python on PATH. Re-open PowerShell after installing and try again."
    }
}
Write-Host ("[+] Python: " + $py.Source)

# --- 2. requests dep -----------------------------------------------
& $py.Source -c "import requests" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[+] installing requests..."
    & $py.Source -m pip install --quiet requests
}

# --- 3. Client key + secret ----------------------------------------
$env:TIKTOK_CLIENT_KEY = "aw9hmk3x2xmhv4mv"
$secretFile = Join-Path $PSScriptRoot ".tiktok_secret"
if (Test-Path $secretFile) {
    $env:TIKTOK_CLIENT_SECRET = (Get-Content $secretFile).Trim()
} else {
    Write-Host ""
    Write-Host "Paste your TikTok Client Secret from the developer dashboard:" -ForegroundColor Cyan
    $sec = Read-Host -AsSecureString
    $env:TIKTOK_CLIENT_SECRET = [System.Net.NetworkCredential]::new("", $sec).Password
    Set-Content -Path $secretFile -Value $env:TIKTOK_CLIENT_SECRET -NoNewline
    Write-Host "[+] secret saved locally to .tiktok_secret (gitignored)"
}

# --- 4. Find a video to upload -------------------------------------
$videoPath = $null
$outputDir = Join-Path $PSScriptRoot "output"
if (Test-Path $outputDir) {
    $videoPath = Get-ChildItem -Path $outputDir -Filter "*.mp4" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $videoPath) {
    Write-Host "[+] no mp4 in output/ - downloading a 5MB sample to use..."
    $sample = Join-Path $PSScriptRoot "sample.mp4"
    Invoke-WebRequest -Uri "https://download.samplelib.com/mp4/sample-5s.mp4" -OutFile $sample
    $videoPath = Get-Item $sample
}
Write-Host ("[+] uploading: " + $videoPath.FullName)

# --- 5. Find the demo .py next to this script ----------------------
$demoPy = Join-Path $PSScriptRoot "tiktok_demo.py"
if (-not (Test-Path $demoPy)) {
    throw "Missing tiktok_demo.py next to this script. Download it from the repo and save it in this same folder."
}

# --- 6. Go ---------------------------------------------------------
Write-Host ""
Write-Host "=== Start your screen recording NOW (Win+G) ===" -ForegroundColor Green
Read-Host "Press Enter when recording is rolling"

& $py.Source $demoPy $videoPath.FullName
