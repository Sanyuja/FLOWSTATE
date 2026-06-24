# =================================================================
# FLOWSTATE -- Windows Setup Script
# Run ONCE in PowerShell as Administrator before using n8n.
# =================================================================
#
# Before running: set CONTENT_BASE, APPROVED_BASE, VAULT_BASE in
# your environment, or edit the $contentBase variables below.
# =================================================================

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  FLOWSTATE -- Setup Script" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ---- CONFIGURE THESE to match your content folder paths ----
$contentBase  = $env:CONTENT_BASE  ?? "D:\your-content-folder"
$approvedBase = $env:APPROVED_BASE ?? "D:\your-content-folder_approved"
$vaultBase    = $env:VAULT_BASE    ?? "D:\your-content-folder_vault"
$scriptsDir   = $env:SCRIPTS_DIR   ?? "$contentBase\scripts"

# ---- Step 1: Create scripts folder ----
Write-Host "[1/5] Creating scripts folder..." -ForegroundColor Yellow
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    Write-Host "      Created: $scriptsDir" -ForegroundColor Green
} else {
    Write-Host "      Already exists: $scriptsDir" -ForegroundColor Gray
}

# ---- Step 2: Create output folder structure ----
Write-Host "[2/5] Creating output folder structure..." -ForegroundColor Yellow
$folders = @(
    "$approvedBase\instagram",
    "$approvedBase\threads",
    "$approvedBase\x",
    "$vaultBase\OF_ready",
    "$vaultBase\watermarked",
    "$vaultBase\reel_review"
)
foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "      Created: $folder" -ForegroundColor Green
    } else {
        Write-Host "      OK: $folder" -ForegroundColor Gray
    }
}

# ---- Step 3: Create pending state files ----
Write-Host "[3/5] Initialising state files..." -ForegroundColor Yellow
$stateFiles = @(
    "$scriptsDir\pending_approvals.json",
    "$scriptsDir\pending_reels.json"
)
foreach ($file in $stateFiles) {
    if (-not (Test-Path $file)) {
        '{}' | Out-File -FilePath $file -Encoding UTF8
        Write-Host "      Created: $file" -ForegroundColor Green
    } else {
        Write-Host "      Already exists: $file" -ForegroundColor Gray
    }
}

# ---- Step 4: Install Sharp in n8n's environment ----
Write-Host "[4/5] Installing Sharp for n8n..." -ForegroundColor Yellow
$n8nPath = npm root -g 2>$null
if ($n8nPath) {
    $n8nDir = Join-Path $n8nPath "n8n"
    if (Test-Path $n8nDir) {
        Write-Host "      Found n8n at: $n8nDir" -ForegroundColor Green
        Push-Location $n8nDir
        npm install sharp --save 2>&1 | Select-Object -Last 3
        Pop-Location
        Write-Host "      Sharp installed in n8n." -ForegroundColor Green
    } else {
        Write-Host "      n8n not found at $n8nDir. Installing Sharp globally..." -ForegroundColor Yellow
        npm install -g sharp 2>&1 | Select-Object -Last 3
    }
} else {
    Write-Host "      npm not found. Install Node.js 20+ first." -ForegroundColor Red
    exit 1
}

$sharpCheck = node -e "require('sharp'); console.log('OK')" 2>&1
if ($sharpCheck -eq "OK") {
    Write-Host "      Sharp verified: working" -ForegroundColor Green
} else {
    Write-Host "      [WARN] Sharp may not be accessible yet. If blur fails in n8n," -ForegroundColor Yellow
    Write-Host "      run: npm install sharp inside $n8nDir" -ForegroundColor Yellow
}

# ---- Step 5: Copy scripts to scripts folder ----
Write-Host "[5/5] Copying scripts to scripts folder..." -ForegroundColor Yellow
$scriptFiles = @("blur.js")
foreach ($scriptFile in $scriptFiles) {
    $src = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\$scriptFile"
    $dst = Join-Path $scriptsDir $scriptFile
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "      Copied: $scriptFile -> $dst" -ForegroundColor Green
    } else {
        Write-Host "      [WARN] $scriptFile not found at $src -- copy it manually to $dst" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Follow docs\credentials-setup.md to get all API keys" -ForegroundColor White
Write-Host "  2. Set environment variables (Machine scope) + restart n8n" -ForegroundColor White
Write-Host "  3. Copy config\persona.example.json -> edit voice brief + folders" -ForegroundColor White
Write-Host "  4. Open n8n at http://localhost:5678" -ForegroundColor White
Write-Host "  5. Import workflows\image_pipeline.json" -ForegroundColor White
Write-Host "  6. Import workflows\approval_handler.json" -ForegroundColor White
Write-Host "  7. Update CONFIGURE THIS sections in each workflow" -ForegroundColor White
Write-Host "  8. Activate both workflows + drop a test image" -ForegroundColor White
Write-Host ""
