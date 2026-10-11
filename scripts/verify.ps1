#requires -Version 5.1
<#
.SYNOPSIS
Generate actual observed evidence for a Windows SCM-managed health service.
- Recovery mode deliberately force-terminates the synthetic test service.
- Reboot is MANUAL and never triggered by this script.
No data is uploaded. Evidence stays on the local machine.
#>
param(
    [ValidateSet("Health", "Recovery", "BeforeReboot", "AfterReboot")]
    [string]$Mode = "Health",
    [string]$EvidencePath = ".\evidence\health.json",
    [string]$BaselinePath = ".\evidence\before-reboot.json"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Name = "VesperaProofRebuild"
$Uri = "http://127.0.0.1:8765/healthz"

function Get-ProofObservation {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$Name'"
    if (-not $svc) { throw "SCM service not registered: $Name" }
    if ($svc.State -ne "Running") { throw "SCM service not running: $($svc.State)" }
    if ($svc.StartMode -ne "Auto") { throw "SCM startup not automatic: $($svc.StartMode)" }
    if ([int]$svc.ProcessId -le 0) { throw "Invalid SCM PID" }
    $response = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 4
    if ($response.status -ne "ok" -or $response.service -ne $Name) {
        throw "Health contract mismatch"
    }
    if ([int]$response.pid -ne [int]$svc.ProcessId) {
        throw "Health endpoint PID does not match SCM PID"
    }
    $os = Get-CimInstance Win32_OperatingSystem
    if ([string]$os.BuildNumber -ne '17763' -or [string]$os.Caption -notmatch 'Windows Server 2019') {
        throw "Wrong target OS: expected Windows Server 2019 (17763), got $($os.Caption) ($($os.BuildNumber))"
    }
    $failureText = (& "$env:WINDIR\System32\sc.exe" qfailure $Name) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw "Unable to read SCM recovery policy" }
    if ($failureText -notmatch "RESTART") { throw "SCM restart action not configured" }
    return [ordered]@{
        captured_at_utc = [DateTime]::UtcNow.ToString('o')
        os_caption = [string]$os.Caption
        os_version = [string]$os.Version
        os_build = [string]$os.BuildNumber
        os_last_boot_utc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
        scm_state = [string]$svc.State
        scm_start_mode = [string]$svc.StartMode
        scm_pid = [int]$svc.ProcessId
        recovery_action_present = $true
        health = [ordered]@{
            status = [string]$response.status
            service = [string]$response.service
            pid = [int]$response.pid
            instance_id = [string]$response.instance_id
            started_at_utc = [string]$response.started_at_utc
        }
    }
}

function Wait-ForFreshInstance([int]$OldPid, [string]$OldInstance) {
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 1
        try {
            $snapshot = Get-ProofObservation
            if ($snapshot.scm_pid -ne $OldPid -and
                $snapshot.health.instance_id -ne $OldInstance) {
                return $snapshot
            }
        } catch {
            # Expected during recovery; retry until deadline.
        }
    }
    throw "No independently healthy replacement instance within 90s"
}

$record = [ordered]@{
    mode = $Mode
    target = "native Windows SCM synthetic proof service"
    observed = Get-ProofObservation
}

switch ($Mode) {
    "Recovery" {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw "Recovery test requires Administrator (force termination)."
        }
        $before = $record.observed
        Write-Warning "Force-terminating ONLY $Name PID $($before.scm_pid) to test SCM recovery."
        Stop-Process -Id $before.scm_pid -Force -ErrorAction Stop
        $record.recovery_after = Wait-ForFreshInstance $before.scm_pid $before.health.instance_id
        $record.recovery_assertions_passed = $true
    }
    "AfterReboot" {
        if (-not (Test-Path $BaselinePath)) { throw "Missing baseline evidence: $BaselinePath" }
        $baseline = Get-Content -LiteralPath $BaselinePath -Raw | ConvertFrom-Json
        if ($baseline.mode -ne "BeforeReboot") { throw "Wrong baseline mode" }
        $previousBoot = [DateTime]::Parse([string]$baseline.observed.os_last_boot_utc).ToUniversalTime()
        $currentBoot = [DateTime]::Parse([string]$record.observed.os_last_boot_utc).ToUniversalTime()
        if ($currentBoot -le $previousBoot) { throw "OS boot time has not advanced; reboot not proven" }
        $record.previous_boot_utc = $previousBoot.ToString('o')
        $record.reboot_assertions_passed = $true
    }
}

$destination = [System.IO.Path]::GetFullPath($EvidencePath)
$parent = [System.IO.Path]::GetDirectoryName($destination)
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $destination -Encoding UTF8
Write-Host "PASS: $Mode ($($record.observed.os_caption), build $($record.observed.os_build))"
Write-Host "Evidence: $destination"
