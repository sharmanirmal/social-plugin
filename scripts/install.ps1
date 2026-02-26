# Social Plugin — Windows installer
# Usage: irm https://raw.githubusercontent.com/nirmalsharma/social-plugin/main/scripts/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "Social Plugin — Installer" -ForegroundColor Cyan
Write-Host ""

# ---- Check Python ----
$python = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
                $python = $cmd
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Host "Python 3.11+ not found." -ForegroundColor Yellow
    $install = Read-Host "Install Python 3.12 via winget? (Y/n)"
    if ($install -ne "n") {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $python = "python3"
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    } else {
        Write-Host "Please install Python 3.11+ and re-run this script." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Using $python" -ForegroundColor Green

# ---- Check/install pipx ----
$hasPipx = Get-Command pipx -ErrorAction SilentlyContinue
if (-not $hasPipx) {
    Write-Host "Installing pipx..." -ForegroundColor Cyan
    & $python -m pip install --user pipx
    & $python -m pipx ensurepath
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
}

Write-Host "pipx available" -ForegroundColor Green

# ---- Install social-plugin ----
Write-Host "Installing social-plugin..." -ForegroundColor Cyan
try {
    pipx install social-plugin
} catch {
    pipx upgrade social-plugin
}

Write-Host "social-plugin installed!" -ForegroundColor Green
Write-Host ""

# ---- Run init wizard ----
Write-Host "Running setup wizard..." -ForegroundColor Cyan
Write-Host ""
social-plugin init
