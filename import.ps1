param(
    [string]$Dump = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root "import.sh"

$drive = $script.Substring(0, 1).ToLower()
$wslScript = "/mnt/$drive" + ($script.Substring(2) -replace "\\", "/")

$argv = @()
if ($Dump) {
    if ($Dump -match '^[A-Za-z]:') {
        $d = $Dump.Substring(0, 1).ToLower()
        $wslDump = "/mnt/$d" + ($Dump.Substring(2) -replace "\\", "/")
    } else {
        $wslDump = $Dump
    }
    $argv += $wslDump
}

wsl.exe -e bash $wslScript @argv
exit $LASTEXITCODE
