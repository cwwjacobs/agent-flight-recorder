#requires -Version 5.1
<#
.SYNOPSIS
Install an isolated native SCM Python service. Requires elevated PowerShell.
Requires machine-wide Python 3.11 x64, accessible by LocalSystem.
WARNING: Installs/modifies a *new* test service and Python environment.
#>
param([string]$PythonExe = "python")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Name = "VesperaProofRebuild"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run from an elevated PowerShell session (Administrator)."
}
if (Get-Service -Name $Name -ErrorAction SilentlyContinue) {
    throw "Service $Name already exists. Review it before making changes."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Write-Host "Installing synthetic test package from $Root"
& $PythonExe -m pip install "$($Root)[windows]"
if ($LASTEXITCODE -ne 0) { throw "Package/pywin32 installation failed" }

# pywin32 may require an elevated post-install for Windows Service support.
$ScriptsDir = (& $PythonExe -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not resolve Python scripts directory" }
$PostInstall = Join-Path $ScriptsDir "pywin32_postinstall.py"
if (Test-Path $PostInstall) {
    & $PythonExe $PostInstall -install
    if ($LASTEXITCODE -ne 0) { throw "pywin32 post-install failed" }
}

& $PythonExe -m ws19proof.windows_service --startup auto install
if ($LASTEXITCODE -ne 0) { throw "SCM service installation failed" }

# sc.exe requires a space after every '= ' option.
& "$env:WINDIR\System32\sc.exe" config $Name start= auto
if ($LASTEXITCODE -ne 0) { throw "Failed to configure automatic startup" }
& "$env:WINDIR\System32\sc.exe" failure $Name reset= 86400 actions= restart/5000/restart/5000/restart/5000
if ($LASTEXITCODE -ne 0) { throw "Failed to configure SCM recovery" }
& "$env:WINDIR\System32\sc.exe" failureflag $Name 1
if ($LASTEXITCODE -ne 0) { throw "Failed to enable SCM failure actions" }
& "$env:WINDIR\System32\sc.exe" start $Name
if ($LASTEXITCODE -ne 0) { throw "Service did not start; inspect Windows Event Viewer" }
Write-Host "Registered $Name with Automatic start and restart-on-failure."
Write-Host "Run .\scripts\verify.ps1 -Mode Health to verify HTTP and SCM identity."
