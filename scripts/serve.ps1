# Runs FloorPlanner locally for testing. Fully static/client-only app -- no backend needed.
# Usage: powershell -File scripts\serve.ps1 [-Port 8794]
param([int]$Port = 8794)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python -m http.server $Port
