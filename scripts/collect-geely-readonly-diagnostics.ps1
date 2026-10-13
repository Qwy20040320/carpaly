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

function Invoke-AdbOptionalReadOnly {
    param([string[]]$Arguments)

    $result = & $adbPath @adbDeviceArgs @Arguments 2>&1
    if ($LASTEXITCODE -ne 0 -or (($result -join "`n") -match '(?i)can.t find service|unknown service|service .* not found')) {
        return @('[not exposed by this Android build]')
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
    Select-String -Pattern '(?i)audio.?focus|focus request|AudioPlaybackConfiguration|attributes:|usage=|content.?type|stream(?:\s|:|=)|volume|device|route|port|strategy|mode|duck|communication|speaker' |
    Select-Object -First 180
Write-Output '--- audio service: focus, streams, volumes, active attributes and routes'
foreach ($line in $audioLines) {
    Protect-DiagnosticLine -Line $line.Line
}

function Write-OptionalFilteredQuery {
    param([string]$Title, [string[]]$Arguments, [string]$Pattern, [int]$Limit = 120)

    Write-Output "--- $Title"
    $result = Invoke-AdbOptionalReadOnly -Arguments $Arguments
    $matches = @($result | Select-String -Pattern $Pattern | Select-Object -First $Limit)
    if ($matches.Count -eq 0) {
        Write-Output '[no matching audio diagnostics exposed]'
        return
    }
    foreach ($line in $matches) {
        Protect-DiagnosticLine -Line $line.Line
    }
}

Write-OptionalFilteredQuery -Title 'AudioFlinger playback tracks and output devices' `
    -Arguments @('shell', 'dumpsys', 'media.audio_flinger') `
    -Pattern '(?i)track|playback|output|device|route|stream|usage|attributes|session|sample.rate|port|mixer|state' -Limit 160
Write-OptionalFilteredQuery -Title 'AudioPolicy devices, routing strategies and volume decisions' `
    -Arguments @('shell', 'dumpsys', 'media.audio_policy') `
    -Pattern '(?i)device|output|input|route|stream|strategy|volume|focus|duck|policy|available|active|communication|speaker|bluetooth' -Limit 160

Write-OptionalFilteredQuery -Title 'Media sessions (state only; metadata/titles are excluded)' `
    -Arguments @('shell', 'dumpsys', 'media_session') `
    -Pattern '(?i)active sessions|playbackstate|state=|active=|package=|owner=|audiofocus|volume' -Limit 80

$logLines = Invoke-AdbReadOnly -Arguments @(
    'logcat', '-d', '-t', '500', '-v', 'time', '-s',
    'AndroidRuntime:E', 'AudioTrack:W', 'AudioFlinger:W', 'AudioPolicy:W',
    'AudioService:W', 'MediaFocusControl:W', 'DiPlay:W', 'DiPlay-MediaKeys:I', 'DiPlay-AudioFocus:I'
)
Write-Output '--- recent app/audio errors'
foreach ($line in $logLines) {
    Protect-DiagnosticLine -Line ([string]$line)
}

Write-Output 'Repeat while parked for baseline music, a navigation prompt, Siri, and a phone call; compare focus, stream, route and volume/ducking lines.'
Write-Output 'Collection complete. No CAN/UDS, broadcast, preference write, permission change, audio setting change, or vehicle-control command was sent.'
