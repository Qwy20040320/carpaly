$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot 'ReleaseSystem.Core.psm1') -Force

$passed = 0
function Assert-True([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
    $script:passed++
}
function Assert-Throws([scriptblock] $Action, [string] $Message) {
    $thrown = $false
    try { & $Action } catch { $thrown = $true }
    if (-not $thrown) { throw $Message }
    $script:passed++
}

$ledger = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\config\android-version-ledger.json') -Raw | ConvertFrom-Json
$entryPath = Join-Path $PSScriptRoot '..\build-release.ps1'
$entryText = Get-Content -LiteralPath $entryPath -Raw
$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($entryPath, [ref]$tokens, [ref]$parseErrors) | Out-Null
Assert-True ($parseErrors.Count -eq 0) 'The top-level release orchestrator has PowerShell parse errors.'
foreach ($mode in @('CheckOnly','SkipTests','PrepareGitHub','PrepareDraft','Status','FullPrepare')) {
    Assert-True ($entryText.Contains("`$${mode}")) "Missing release mode parameter/use: $mode"
}
Assert-True ($entryText -notmatch '(?i)gh\s+release\s+(create|upload)|AUTO_CREATE_TAG\s*=\s*''true''|prepare-release-draft\.sh') 'Local orchestrator contains a direct remote Release mutation path.'
Assert-True ((ConvertTo-CarPalyFingerprint 'D9:B3:29:52:5F:C1:EF:21:C3:65:FA:B7:2C:10:36:75:27:CC:03:82:97:C4:F3:0E:AA:22:B2:20:74:29:13:9E') -eq $ledger.releaseCertificateSha256) 'Fingerprint normalization failed.'
Assert-Throws { ConvertTo-CarPalyFingerprint 'not-a-fingerprint' | Out-Null } 'Malformed signer fingerprint was accepted.'
Assert-True ((Get-CarPalySignerForVersion $ledger 40) -eq $ledger.signingEpochs[0].certificateSha256) 'Legacy signing epoch selection failed.'
Assert-True ((Get-CarPalySignerForVersion $ledger 44) -eq $ledger.signingEpochs[1].certificateSha256) 'Active signing epoch selection failed.'
$gapLedger = $ledger | ConvertTo-Json -Depth 8 | ConvertFrom-Json
$gapLedger.signingEpochs = @($ledger.signingEpochs[0])
Assert-Throws { Get-CarPalySignerForVersion $gapLedger 44 | Out-Null } 'Missing signing epoch was accepted.'

$secretText = 'PASSWORD=HiddenValue token:abcdefghijklmnop'
$redacted = Protect-CarPalyText $secretText
Assert-True ($redacted -notmatch 'HiddenValue|abcdefghijklmnop') 'Sensitive sample was not redacted.'
Assert-True ($redacted -match '\[REDACTED\]') 'Redaction marker was not emitted.'

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("carpaly-release-test-" + [guid]::NewGuid().ToString('N'))
$stateFile = Join-Path $tempRoot 'state.json'
try {
    Set-CarPalyLocalReleaseState -Path $stateFile -VersionName '1.1.57' -State 'SOURCE_READY' -Evidence 'commit-sha=abc123' -Commit 'abc123'
    $saved = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    Assert-True ($saved.currentState -eq 'SOURCE_READY' -and $saved.events.Count -eq 1) 'State was not persisted.'
    Assert-Throws { Set-CarPalyLocalReleaseState -Path $stateFile -VersionName '1.1.58' -State 'PR_CREATED' -Evidence 'pr=1' } 'Conflicting version state was overwritten.'
    Assert-Throws { Set-CarPalyLocalReleaseState -Path $stateFile -VersionName '1.1.57' -State 'CI_PASSED' -Evidence '' } 'Evidence-free state was accepted.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}

Write-Output "POWERSHELL_RELEASE_CORE_TESTS=PASS count=$passed"
