param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root "run.sh"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL2 not found. Install it first: wsl --install"
}

$drive = $script.Substring(0, 1).ToLower()
$wslScript = "/mnt/$drive" + ($script.Substring(2) -replace "\\", "/")

Write-Host "Starting QEMU in WSL; opening http://127.0.0.1:8099/ ..."
Start-Sleep -Milliseconds 500
Start-Process "http://127.0.0.1:8099/"
wsl.exe -e bash $wslScript web
exit $LASTEXITCODE
