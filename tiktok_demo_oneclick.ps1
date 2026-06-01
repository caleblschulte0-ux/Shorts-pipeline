# One-click TikTok demo runner. Tested on Windows PowerShell 5.1.
# Pure ASCII, no `??`, no `$ErrorActionPreference=Stop` (it makes
# PowerShell treat Python's stderr as a fatal error).
#
# Use: right-click this file -> Run with PowerShell. Or:
#   Set-ExecutionPolicy -Scope Process Bypass -Force; .\tiktok_demo_oneclick.ps1

# --- 1. Find Python ------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "Python not found. Opening python.org downloader." -ForegroundColor Yellow
    Start-Process "https://www.python.org/downloads/"
    Read-Host "Install Python (check 'Add Python to PATH'), then press Enter"
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) {
        Write-Host "Still no python on PATH. Re-open PowerShell after installing." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host ("[+] Python: " + $py.Source)

# --- 2. requests dep (idempotent install; pip stderr is harmless) --
Write-Host "[+] ensuring 'requests' is installed..."
& $py.Source -m pip install --quiet --disable-pip-version-check requests 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed. Run 'python -m pip install requests' manually and re-run." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 3. Client key + secret ----------------------------------------
$env:TIKTOK_CLIENT_KEY = "aw9hmk3x2xmhv4mv"
$secretFile = Join-Path $PSScriptRoot ".tiktok_secret"
if (Test-Path $secretFile) {
    $env:TIKTOK_CLIENT_SECRET = (Get-Content $secretFile).Trim()
} else {
    Write-Host ""
    Write-Host "Paste your TikTok Client Secret from the dev dashboard:" -ForegroundColor Cyan
    $sec = Read-Host -AsSecureString
    $env:TIKTOK_CLIENT_SECRET = [System.Net.NetworkCredential]::new("", $sec).Password
    Set-Content -Path $secretFile -Value $env:TIKTOK_CLIENT_SECRET -NoNewline
    Write-Host "[+] secret saved to .tiktok_secret (gitignored)"
}

# --- 4. Find a video to upload -------------------------------------
$videoPath = $null
$outputDir = Join-Path $PSScriptRoot "output"
if (Test-Path $outputDir) {
    $videoPath = Get-ChildItem -Path $outputDir -Filter "*.mp4" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $videoPath) {
    $sample = Join-Path $PSScriptRoot "sample.mp4"
    if (-not (Test-Path $sample)) {
        Write-Host "[+] no mp4 nearby - downloading a 5MB sample..."
        Invoke-WebRequest -Uri "https://download.samplelib.com/mp4/sample-5s.mp4" -OutFile $sample
    }
    $videoPath = Get-Item $sample
}
Write-Host ("[+] uploading: " + $videoPath.FullName)

# --- 5. Find the demo .py next to this script ----------------------
$demoPy = Join-Path $PSScriptRoot "tiktok_demo.py"
if (-not (Test-Path $demoPy)) {
    Write-Host "Missing tiktok_demo.py next to this script. Downloading the latest..."
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/caleblschulte0-ux/Shorts-pipeline/main/tiktok_demo.py" -OutFile $demoPy
}

# --- 6. Go ---------------------------------------------------------
Write-Host ""
Write-Host "=== Start your screen recording NOW (Win+G) ===" -ForegroundColor Green
Read-Host "Press Enter when recording is rolling"

& $py.Source $demoPy $videoPath.FullName
$rc = $LASTEXITCODE

Write-Host ""
if ($rc -eq 0) {
    Write-Host "Done. Stop your recording and trim it for TikTok upload." -ForegroundColor Green
} else {
    Write-Host ("demo exited with code " + $rc) -ForegroundColor Yellow
}
Read-Host "Press Enter to close"
