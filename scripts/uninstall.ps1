#requires -Version 5.1
<#
.SYNOPSIS
Stop and remove ONLY the VesperaProofRebuild test service.
Does not uninstall Python, pywin32, or delete evidence files.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Name = "VesperaProofRebuild"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run elevated PowerShell."
}
$svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
if (-not $svc) { Write-Host "$Name is not installed"; return }
if ($svc.Status -ne 'Stopped') {
    Stop-Service -Name $Name -ErrorAction Stop
    (Get-Service -Name $Name).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
}
& "$env:WINDIR\System32\sc.exe" delete $Name
if ($LASTEXITCODE -ne 0) { throw "Service removal failed" }
Write-Host "Removed test service: $Name"
