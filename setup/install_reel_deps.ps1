# =================================================================
# FLOWSTATE -- Reel Creator Dependency Setup
# Run ONCE in PowerShell as Administrator
# =================================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  FLOWSTATE -- Reel Creator Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$scriptsDir = $env:SCRIPTS_DIR ?? "D:\your-content-folder\scripts"
$vaultBase  = $env:VAULT_BASE  ?? "D:\your-content-folder_vault"

# --- Check Python ---
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      OK: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Python not found." -ForegroundColor Red
    Write-Host "      Download from https://python.org (check 'Add to PATH' during install)" -ForegroundColor Yellow
    exit 1
}

# --- Check/Install FFmpeg ---
Write-Host "[2/4] Checking FFmpeg..." -ForegroundColor Yellow
try {
    $ffVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "      OK: $ffVersion" -ForegroundColor Green
} catch {
    Write-Host "      FFmpeg not found. Installing via winget..." -ForegroundColor Yellow
    try {
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        Write-Host "      FFmpeg installed. Restart PowerShell to use it." -ForegroundColor Green
    } catch {
        Write-Host "      Could not auto-install FFmpeg." -ForegroundColor Red
        Write-Host "      Download from: https://ffmpeg.org/download.html" -ForegroundColor Yellow
        Write-Host "      Extract and add the bin\ folder to your Windows PATH." -ForegroundColor Yellow
    }
}

# --- Copy reel_creator.py to scripts folder ---
Write-Host "[3/4] Copying reel_creator.py to scripts folder..." -ForegroundColor Yellow
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
}
$reelSrc = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\reel_creator.py"
$reelDst = Join-Path $scriptsDir "reel_creator.py"
if (Test-Path $reelSrc) {
    Copy-Item $reelSrc $reelDst -Force
    Write-Host "      Copied: $reelDst" -ForegroundColor Green
} else {
    Write-Host "      reel_creator.py not found at $reelSrc" -ForegroundColor Yellow
    Write-Host "      Copy it manually to: $reelDst" -ForegroundColor Yellow
}

# --- Create reel state files ---
Write-Host "[4/4] Creating reel state files..." -ForegroundColor Yellow
$reviewDir    = "$vaultBase\reel_review"
$pendingReels = "$scriptsDir\pending_reels.json"
if (-not (Test-Path $reviewDir)) {
    New-Item -ItemType Directory -Path $reviewDir -Force | Out-Null
    Write-Host "      Created: $reviewDir" -ForegroundColor Green
}
if (-not (Test-Path $pendingReels)) {
    '{}' | Out-File -FilePath $pendingReels -Encoding UTF8
    Write-Host "      Created: $pendingReels" -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Reel Creator setup complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Import workflows\reel_creator.json into n8n" -ForegroundColor White
Write-Host "  2. Update the CONFIGURE THIS sections" -ForegroundColor White
Write-Host "  3. Activate the workflow" -ForegroundColor White
Write-Host "  4. Test: send WhatsApp message 'IDEA: lifestyle, golden hour, 20s VO'" -ForegroundColor White
Write-Host ""
