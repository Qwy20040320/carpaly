[CmdletBinding()]
param(
    [string]$Serial
)

$ErrorActionPreference = 'Stop'

$sdkPath = if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { $env:ANDROID_HOME }
if (-not $sdkPath) {
    throw 'Set ANDROID_SDK_ROOT or ANDROID_HOME to the installed Android SDK directory.'
}

$adbPath = Join-Path $sdkPath 'platform-tools/adb.exe'
if (-not (Test-Path -LiteralPath $adbPath -PathType Leaf)) {
    throw "Android Debug Bridge was not found at the configured SDK path."
}

$adbDeviceArgs = @()
if ($Serial) {
    $adbDeviceArgs = @('-s', $Serial)
}

function Invoke-AdbReadOnly {
    param([string[]]$Arguments)

    $result = & $adbPath @adbDeviceArgs @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Read-only ADB query failed: adb $($Arguments -join ' ')"
    }
    return $result
}

function Protect-DiagnosticLine {
    param([string]$Line)

    $safe = $Line -replace '(?i)\b(token|password|authorization|ssid|bssid|serial(?:number)?|vehicleid)\b(\s*[=:]\s*)\S+', '$1$2[redacted]'
    $safe = $safe -replace '(?i)\bvin\s*[=:]\s*\S+', 'VIN=[redacted]'
    $safe = $safe -replace '\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b', '[ip]'
    $safe = $safe -replace '(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b', '[mac]'
    $safe = $safe -replace '\b[A-HJ-NPR-Z0-9]{17}\b', '[vehicle-id]'
    return $safe
}

function Write-Query {
    param([string]$Title, [string[]]$Arguments)

    Write-Output "--- $Title"
    foreach ($line in (Invoke-AdbReadOnly -Arguments $Arguments)) {
        Protect-DiagnosticLine -Line ([string]$line)
    }
}

Write-Output 'Read-only collection: this script uses only adb shell getprop, dumpsys, and logcat -d queries.'
Write-Query -Title 'device state' -Arguments @('get-state')
Write-Query -Title 'Android release' -Arguments @('shell', 'getprop', 'ro.build.version.release')
Write-Query -Title 'Android API level' -Arguments @('shell', 'getprop', 'ro.build.version.sdk')
Write-Query -Title 'head-unit manufacturer' -Arguments @('shell', 'getprop', 'ro.product.manufacturer')
Write-Query -Title 'head-unit model' -Arguments @('shell', 'getprop', 'ro.product.model')

$packageLines = Invoke-AdbReadOnly -Arguments @('shell', 'dumpsys', 'package', 'com.shihab.diplay.hudtest') |
    Select-String -Pattern 'versionName=|versionCode=|targetSdk=|minSdk=|requested permissions:|install permissions:' |
    Select-Object -First 40
Write-Output '--- CarPaly package metadata'
foreach ($line in $packageLines) {
    Protect-DiagnosticLine -Line $line.Line
}

$audioLines = Invoke-AdbReadOnly -Arguments @('shell', 'dumpsys', 'audio') |
    Select-String -Pattern 'Audio Focus|Focus request|AudioPlaybackConfiguration|attributes:|usage=|stream:|AudioTrack|device=' |
    Select-Object -First 100
Write-Output '--- audio routing snapshot'
foreach ($line in $audioLines) {
    Protect-DiagnosticLine -Line $line.Line
}

$logLines = Invoke-AdbReadOnly -Arguments @('logcat', '-d', '-t', '250', '-s', 'AndroidRuntime:E', 'AudioTrack:W', 'DiPlay:W')
Write-Output '--- recent app/audio errors'
foreach ($line in $logLines) {
    Protect-DiagnosticLine -Line ([string]$line)
}

Write-Output 'Collection complete. No CAN/UDS, broadcast, preference write, permission change, or vehicle-control command was sent.'
