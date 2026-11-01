param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$setup = Join-Path $root "setup.sh"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL2 not found. Install it first: wsl --install"
}

$drive = $setup.Substring(0, 1).ToLower()
$wslSetup = "/mnt/$drive" + ($setup.Substring(2) -replace "\\", "/")

Write-Host "Building QEMU inside WSL (this takes 10-20 minutes) ..."
wsl.exe -e bash $wslSetup
exit $LASTEXITCODE
