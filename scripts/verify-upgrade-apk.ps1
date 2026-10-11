param(
    [Parameter(Mandatory = $true)]
    [string] $ApkPath,

    [string] $AuthenticationAssetsRoot = $env:DIPLAY_AUTH_ASSETS_DIR,
    [string] $AndroidSdkPath = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { 'D:\AndroidSdk' }),
    [string] $ReportPath,

    [switch] $RecordDelivery
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$ledgerPath = Join-Path $projectRoot 'config\android-version-ledger.json'
$gradlePath = Join-Path $projectRoot 'mobile\build.gradle.kts'
$ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$gradle = Get-Content -LiteralPath $gradlePath -Raw
$apk = (Resolve-Path -LiteralPath $ApkPath).Path
if (-not $ReportPath) { $ReportPath = "$apk.verification.json" }

$expectedPackage = 'com.shihab.diplay.hudtest'
$expectedSigner = '4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90'
$expectedName = [string] $ledger.current.versionName
$expectedCode = [int] $ledger.current.versionCode
$baselineCode = [int] $ledger.highestObservedVersionCode
$buildTools = Join-Path $AndroidSdkPath 'build-tools\36.0.0'
$aapt = Join-Path $buildTools 'aapt.exe'
$apksigner = Join-Path $buildTools 'apksigner.bat'

foreach ($tool in @($aapt, $apksigner)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Required Android SDK verification tool is missing: $tool"
    }
}
if ($expectedPackage -notmatch '^com\.shihab\.diplay\.hudtest$' -or
    $ledger.applicationId -ne $expectedPackage -or
    $gradle -notmatch ('(?m)^\s*applicationId\s*=\s*"' + [regex]::Escape($expectedPackage) + '"\s*$')) {
    throw 'Project applicationId does not match the permanent upgrade identity.'
}
if ($expectedCode -le $baselineCode -or
    $gradle -notmatch ('(?m)^\s*versionCode\s*=\s*' + $expectedCode + '\s*$') -or
    $gradle -notmatch ('(?m)^\s*versionName\s*=\s*"' + [regex]::Escape($expectedName) + '"\s*$')) {
    throw 'Gradle version metadata is not the reserved, monotonic user-delivery version.'
}
if ($ledger.releaseCertificateSha256 -ne $expectedSigner -or $gradle -notmatch [regex]::Escape($expectedSigner)) {
    throw 'The fixed v1.1.4 Release signer pin is absent or inconsistent.'
}
if (-not $AuthenticationAssetsRoot) {
    throw 'DIPLAY_AUTH_ASSETS_DIR is required to compare packaged runtime authentication files.'
}

$checks = [ordered]@{}
$zip = $null
try {
    $signatureOutput = & $apksigner verify --verbose --print-certs $apk 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Android APK signature verification failed.' }
    $signatureText = $signatureOutput -join "`n"
    $signerMatch = [regex]::Match($signatureText, '(?m)^Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F:]+)\s*$')
    if (-not $signerMatch.Success) { throw 'APK signer fingerprint was not reported.' }
    if ($signatureText -notmatch '(?m)^Number of signers:\s*1\s*$') { throw 'APK must have exactly one signing identity.' }
    $signerSha256 = ($signerMatch.Groups[1].Value -replace ':', '').ToLowerInvariant()
    if ($signerSha256 -ne $expectedSigner) { throw 'APK signer is not the fixed v1.1.4 Release identity.' }
    $schemeMatch = [regex]::Match($signatureText, '(?m)^Verified using v2 scheme \(APK Signature Scheme v2\): true\s*$')
    if (-not $schemeMatch.Success) { throw 'APK Signature Scheme v2 was not verified.' }
    $checks['APK_SIGNATURE'] = 'PASS'

    $badgingOutput = & $aapt dump badging $apk 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Android APK metadata inspection failed.' }
    $badging = $badgingOutput -join "`n"
    $packageMatch = [regex]::Match($badging, "(?m)^package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'")
    if (-not $packageMatch.Success) { throw 'APK package/version metadata could not be parsed.' }
    $packageName = $packageMatch.Groups[1].Value
    $versionCode = [int] $packageMatch.Groups[2].Value
    $versionName = $packageMatch.Groups[3].Value
    if ($packageName -ne $expectedPackage) { throw 'APK applicationId differs from the installed upgrade identity.' }
    if ($versionName -ne $expectedName -or $versionCode -ne $expectedCode -or $versionCode -le $baselineCode) {
        throw 'APK versionName/versionCode does not match the reserved monotonic version.'
    }
    $minSdkMatch = [regex]::Match($badging, "(?m)^sdkVersion:'([0-9]+)'")
    if (-not $minSdkMatch.Success -or [int] $minSdkMatch.Groups[1].Value -lt 25) {
        throw 'APK minSdk is not compatible with the supported head-unit baseline (API 25).'
    }
    $checks['PACKAGE_NAME_MATCH'] = 'PASS'
    $checks['VERSION_CODE_INCREMENT'] = 'PASS'
    $checks['MIN_SDK'] = 'PASS'

    $manifestOutput = & $aapt dump xmltree $apk AndroidManifest.xml 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'AndroidManifest.xml could not be inspected.' }
    if (($manifestOutput -join "`n") -match 'android:debuggable') {
        throw 'Debuggable APKs are not eligible as user upgrade-test packages.'
    }
    $checks['RELEASE_VARIANT_NOT_DEBUGGABLE'] = 'PASS'

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($apk)
    $entries = @($zip.Entries)
    $abiNames = @($entries | ForEach-Object {
        if ($_.FullName -match '^lib/([^/]+)/') { $Matches[1] }
    } | Sort-Object -Unique)
    if ($abiNames -notcontains 'arm64-v8a') { throw 'APK does not include the required arm64-v8a native ABI.' }
    if ($entries | Where-Object { $_.FullName -match '\.(p12|pfx|jks|keystore)$' }) {
        throw 'APK unexpectedly contains a Release keystore file.'
    }

    $authRoot = (Resolve-Path -LiteralPath $AuthenticationAssetsRoot).Path
    foreach ($name in @('identity.pk8', 'certificate.p7b')) {
        $sourcePath = Join-Path $authRoot "offline-mfi\$name"
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { throw "Authorized runtime input is missing: offline-mfi\$name" }
        $entry = $zip.GetEntry("assets/offline-mfi/$name")
        if (-not $entry) { throw "Standalone APK is missing assets/offline-mfi/$name" }
        $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $entryStream = $entry.Open()
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { $packagedHash = -join ($sha.ComputeHash($entryStream) | ForEach-Object { $_.ToString('x2') }) }
            finally { $sha.Dispose() }
        }
        finally { $entryStream.Dispose() }
        if ($packagedHash -ne $sourceHash) { throw "Packaged runtime input does not match the authorized local input: $name" }
    }
    $checks['AUTH_ASSETS_MATCH_LOCAL_INPUTS'] = 'PASS'
    $checks['NATIVE_ABI'] = 'PASS'

    # Force full decompression of every ZIP entry, in addition to apksigner's digest checks.
    foreach ($entry in $entries) {
        if ($entry.Length -eq 0) { continue }
        $stream = $entry.Open()
        try {
            $buffer = New-Object byte[] 65536
            while ($stream.Read($buffer, 0, $buffer.Length) -gt 0) { }
        }
        finally { $stream.Dispose() }
    }
    $checks['APK_ZIP_INTEGRITY'] = 'PASS'
    $checks['SIGNING_CERTIFICATE_MATCH'] = 'PASS'
    $checks['USER_DATA_PRESERVATION'] = 'NOT_TESTED'

    $apkSha256 = (Get-FileHash -LiteralPath $apk -Algorithm SHA256).Hash.ToLowerInvariant()
    $allocation = @($ledger.allocations | Where-Object { $_.versionName -eq $versionName -and $_.versionCode -eq $versionCode }) | Select-Object -First 1
    if (-not $allocation) { throw 'APK version does not have a unique allocation in the version ledger.' }
    if ($allocation.artifactSha256 -and $allocation.artifactSha256 -ne $apkSha256) {
        throw 'This version already has a delivered APK with different bytes; allocate the next version instead.'
    }
    if ($RecordDelivery -and -not $allocation.artifactSha256) {
        $allocation.artifactSha256 = $apkSha256
        $allocation.status = 'delivered'
        [IO.File]::WriteAllText(
            $ledgerPath,
            (($ledger | ConvertTo-Json -Depth 8) + "`n"),
            [Text.UTF8Encoding]::new($false)
        )
    }
    $checks['VERSION_BINARY_IMMUTABILITY'] = if ($allocation.artifactSha256) { 'PASS' } elseif ($RecordDelivery) { 'PASS' } else { 'NOT_RECORDED' }
    $report = [ordered]@{
        status = 'PASS'
        apk = [IO.Path]::GetFileName($apk)
        packageName = $packageName
        versionName = $versionName
        versionCode = $versionCode
        minSdk = [int] $minSdkMatch.Groups[1].Value
        abis = $abiNames
        bytes = (Get-Item -LiteralPath $apk).Length
        apkSha256 = $apkSha256
        signerCertificateSha256 = $signerSha256
        versionBinarySha256 = $apkSha256
        checks = $checks
        realVehicleAndCarPlay = 'NOT_TESTED'
    }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    Write-Output "APK_VERIFICATION=PASS report=$ReportPath"
}
catch {
    $failure = $_.Exception.Message
    $report = [ordered]@{ status = 'FAIL'; apk = [IO.Path]::GetFileName($apk); checks = $checks; error = $failure }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    throw
}
finally {
    if ($zip) { $zip.Dispose() }
}
