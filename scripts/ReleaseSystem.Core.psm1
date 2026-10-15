Set-StrictMode -Version Latest

function ConvertTo-CarPalyFingerprint {
    param([Parameter(Mandatory = $true)][string] $Value)
    $normalized = ($Value -replace '^(?i)sha256\s*[:=]\s*', '' -replace '[:\s]', '').ToLowerInvariant()
    if ($normalized -notmatch '^[0-9a-f]{64}$') {
        throw 'Certificate SHA-256 must be exactly 32 bytes.'
    }
    return $normalized
}

function Get-CarPalySignerForVersion {
    param(
        [Parameter(Mandatory = $true)] $Ledger,
        [Parameter(Mandatory = $true)][int] $VersionCode
    )
    $matches = @($Ledger.signingEpochs | Where-Object {
        [int] $_.minVersionCode -le $VersionCode -and
        ($null -eq $_.maxVersionCode -or [int] $_.maxVersionCode -ge $VersionCode)
    })
    if ($matches.Count -ne 1) { throw 'Version code does not map to one reviewed signing epoch.' }
    return ConvertTo-CarPalyFingerprint ([string] $matches[0].certificateSha256)
}

function Protect-CarPalyText {
    param([AllowEmptyString()][string] $Text)
    if ($null -eq $Text) { return '' }
    $safe = $Text
    $safe = [regex]::Replace($safe, '(?i)(password|passwd|secret|token|private[_ -]?key|keystore[_ -]?base64)(\s*[:=]\s*)[^\s,;]+', '$1$2[REDACTED]')
    $safe = [regex]::Replace($safe, '(?i)-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----', '[REDACTED PRIVATE KEY]')
    $safe = [regex]::Replace($safe, '\b[A-Za-z0-9+/]{80,}={0,2}\b', '[REDACTED LONG TOKEN]')
    return $safe
}

function Set-CarPalyLocalReleaseState {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $VersionName,
        [Parameter(Mandatory = $true)][string] $State,
        [Parameter(Mandatory = $true)][string] $Evidence,
        [string] $Commit = ''
    )
    if ([string]::IsNullOrWhiteSpace($Evidence)) { throw 'A release state requires concrete evidence.' }
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $document = [ordered]@{
        schemaVersion = 1
        versionName = $VersionName
        currentState = $State
        sourceCommit = $Commit
        updatedAtUtc = [DateTime]::UtcNow.ToString('o')
        events = @()
    }
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        try {
            $existing = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
            if ($existing.versionName -ne $VersionName) { throw 'Existing local state belongs to another version.' }
            $document.sourceCommit = if ($Commit) { $Commit } else { [string] $existing.sourceCommit }
            $document.events = @($existing.events)
        }
        catch { throw 'Existing local release state is unreadable or conflicts with this version.' }
    }
    $document.events += [ordered]@{
        state = $State
        evidence = Protect-CarPalyText $Evidence
        commit = $Commit
        timestampUtc = [DateTime]::UtcNow.ToString('o')
    }
    $temporary = "$Path.tmp"
    [IO.File]::WriteAllText($temporary, (($document | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Assert-CarPalyNativeSuccess {
    param([Parameter(Mandatory = $true)][string] $Operation)
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed with exit code $LASTEXITCODE." }
}

Export-ModuleMember -Function ConvertTo-CarPalyFingerprint, Get-CarPalySignerForVersion, Protect-CarPalyText, Set-CarPalyLocalReleaseState, Assert-CarPalyNativeSuccess
