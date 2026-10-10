[CmdletBinding()]
param(
    [string]$Serial,
    [string]$SdkRoot,
    [ValidateRange(1, 20)]
    [int]$Cycles = 1,
    [switch]$RestartBetweenCycles
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$applicationId = 'com.shihab.diplay.hudtest'
$activityName = 'com.shilapi.xcertplay.DiPlayActivity'

$adbCommand = Get-Command adb -ErrorAction SilentlyContinue
$adbPath = if ($adbCommand) { $adbCommand.Source } else { $null }
if (-not $adbPath) {
    $defaultSdkRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Android/Sdk' } else { $null }
    foreach ($sdkRoot in @($SdkRoot, $env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, $defaultSdkRoot)) {
        if ($sdkRoot) {
            $candidate = Join-Path $sdkRoot 'platform-tools/adb.exe'
            if (Test-Path -LiteralPath $candidate) {
                $adbPath = $candidate
                break
            }
        }
    }
}
if (-not $adbPath) {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $localPropertiesPath = Join-Path $repositoryRoot 'local.properties'
    if (Test-Path -LiteralPath $localPropertiesPath) {
        $sdkLine = Get-Content -LiteralPath $localPropertiesPath |
            Where-Object { $_ -match '^\s*sdk\.dir\s*=' } |
            Select-Object -First 1
        if ($sdkLine -and $sdkLine -match '^\s*sdk\.dir\s*=(.*)$') {
            $sdkRoot = $Matches[1].Trim() -replace '\\:', ':' -replace '\\\\', '\'
            $candidate = Join-Path $sdkRoot 'platform-tools/adb.exe'
            if (Test-Path -LiteralPath $candidate) {
                $adbPath = $candidate
            }
        }
    }
}
if (-not $adbPath) {
    throw 'adb was not found. Add Android platform-tools to PATH or set ANDROID_HOME.'
}

function Invoke-AdbText {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $result = & $script:adbPath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "adb command failed (exit $LASTEXITCODE): adb $($Arguments -join ' ')`n$($result -join "`n")"
    }
    return ($result -join "`n").Trim()
}

$deviceOutput = Invoke-AdbText -Arguments @('devices')
$onlineEmulators = @(
    $deviceOutput -split "`r?`n" |
        ForEach-Object {
            if ($_ -match '^\s*(emulator-\d+)\s+device\s*$') { $Matches[1] }
        }
)

if (-not $Serial) {
    if ($onlineEmulators.Count -ne 1) {
        throw "Expected exactly one booted Android emulator; found $($onlineEmulators.Count). Pass -Serial emulator-N to select one. This script never starts an emulator."
    }
    $Serial = $onlineEmulators[0]
}
if ($Serial -notmatch '^emulator-\d+$' -or $Serial -notin $onlineEmulators) {
    throw 'This smoke test only targets an already-online Android Emulator serial (emulator-N); physical devices are not accepted.'
}

$bootCompleted = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'getprop', 'sys.boot_completed')
if ($bootCompleted -ne '1') {
    throw 'The selected emulator has not completed booting.'
}

$systemLocale = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'getprop', 'persist.sys.locale')
$deviceConfig = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'am', 'get-config')
if (($systemLocale, $deviceConfig -join "`n") -notmatch '(?i)zh(?:[-_]r?CN|[-_]Hans(?:[-_]CN)?)') {
    throw "The emulator is not configured for Simplified Chinese. persist.sys.locale=$systemLocale"
}

$sdk = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'getprop', 'ro.build.version.sdk')
$abi = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'getprop', 'ro.product.cpu.abi')
$packagePath = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'pm', 'path', $applicationId)
if ($packagePath -notmatch '(?m)^package:') {
    throw "CarPaly is not installed on $Serial ($applicationId). This script does not install APKs."
}

$packageInfo = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'dumpsys', 'package', $applicationId)
$versionName = if ($packageInfo -match '(?m)\bversionName=([^\s]+)') { $Matches[1] } else { 'unknown' }
$versionCode = if ($packageInfo -match '(?m)\bversionCode=(\d+)') { $Matches[1] } else { 'unknown' }

Write-Host "Emulator: API $sdk / $abi / Simplified Chinese"
Write-Host "CarPaly: $applicationId $versionName ($versionCode)"
Write-Host 'No APK installation, data clearing, log upload, vehicle command, or emulator launch is performed.'

for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    if ($cycle -gt 1 -and $RestartBetweenCycles) {
        [void](Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'am', 'force-stop', $applicationId))
        Start-Sleep -Milliseconds 500
    }

    $launchOutput = Invoke-AdbText -Arguments @(
        '-s', $Serial, 'shell', 'am', 'start', '-W', '-n', "$applicationId/$activityName"
    )
    if ($launchOutput -notmatch '(?m)^Status:\s*ok\s*$') {
        throw "Launch cycle $cycle was not accepted by Android:`n$launchOutput"
    }

    $foreground = ''
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $activityDump = Invoke-AdbText -Arguments @('-s', $Serial, 'shell', 'dumpsys', 'activity', 'activities')
        $match = [regex]::Match($activityDump, '(?m)^\s*topResumedActivity=.*$')
        if ($match.Success) { $foreground = $match.Value.Trim() }
        if ($foreground -match [regex]::Escape($activityName)) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($foreground -notmatch [regex]::Escape($activityName)) {
        throw "CarPaly launch was accepted, but its main activity did not remain foreground after cycle $cycle. Foreground: $foreground"
    }
    Write-Host "PASS: visible CarPaly activity resumed (cycle $cycle/$Cycles)."
}

Write-Host 'PASS: emulator smoke checks completed.'
