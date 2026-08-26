# Hermes TUI installation script for Windows
#Requires -Version 5.1
# Run with: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

function Write-Info($msg)  { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Err($msg)   { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Check Python
try {
    $pyVersion = & python --version 2>&1
    if ($pyVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Write-Err "Python 3.11+ is required. Found $pyVersion."
            exit 1
        }
        Write-Ok "$pyVersion found."
    } else {
        Write-Err "Could not determine Python version."
        exit 1
    }
} catch {
    Write-Err "Python 3 is required but not found. Install Python 3.11+ from https://python.org"
    exit 1
}

# Prefer pipx
$pipx = Get-Command pipx -ErrorAction SilentlyContinue
if ($pipx) {
    Write-Info "Installing Hermes TUI with pipx..."
    pipx install hermes-tui
} else {
    Write-Info "pipx not found. Installing with pip..."
    Write-Info "Consider installing pipx: https://pipx.pypa.io/"
    python -m pip install --user hermes-tui
}

Write-Ok "Installation complete!"
Write-Info "Run 'hermes-tui chat' to start."
