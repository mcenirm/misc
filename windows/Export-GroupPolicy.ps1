#Requires -RunAsAdministrator

[CmdletBinding()]
param (
    [string]
    $GroupPolicyPath = "$env:SystemRoot\System32\GroupPolicy",

    [Parameter(Mandatory)]
    [string]
    $OutPath,

    [string]
    $Label = "local_gpo_${env:COMPUTERNAME}_$(Get-Date -Format 'yyyy-MM-dd-hhmmss')",

    [string]
    $LgpoExe = 'lgpo.exe'
)

if (-not (Test-Path -Path $OutPath -PathType Container)) {
    Write-Error -ErrorAction Stop -Message "OutPath '$OutPath' should be an existing directory"
    return
}

$outDir = New-Item -ErrorAction Stop -Verbose -Path $OutPath\$Label -ItemType Directory
$copyArgs = @{
    ErrorAction = 'Stop'
    Verbose     = $true
    Recurse     = $true
    PassThru    = $true
    Exclude     = 'DataStore'   # Ignore AD GPO cache
    Path        = "$GroupPolicyPath\*"
    Destination = "$outDir"
}
$copiedItems = Copy-Item @copyArgs

$didWeSeeTheseExpectedFiles = @{
    '.\Machine\comment.cmtx'                         = $false
    '.\Machine\Registry.pol'                         = $false
    '.\Machine\Microsoft\Windows NT\Audit\audit.csv' = $false
    '.\User\comment.cmtx'                            = $false
    '.\User\Registry.pol'                            = $false
    '.\GPT.INI'                                      = $false
}
foreach ($item in $copiedItems) {
    if ($item -is [System.IO.FileInfo]) {
        $relPath = Resolve-Path -Relative -RelativeBasePath $outDir -Path $item
        if ($didWeSeeTheseExpectedFiles.ContainsKey($relPath)) {
            $didWeSeeTheseExpectedFiles.$relPath = $true
            if ($item.Name -eq 'registry.pol') {
                $lgpoParseFlag = switch ($item.Directory.Name) {
                    'Machine' { '/m' }
                    'User' { '/u' }
                    default { $null }
                }
                if ($null -ne $lgpoParseFlag) {
                    $polText = "${item}.txt"
                    $lgpoArgs = ('/parse', '/q', $lgpoParseFlag, $item)
                    & $LgpoExe @lgpoArgs > $polText
                    if (0 -ne $LASTEXITCODE) {
                        Write-Error -ErrorAction Stop "Failed with error code ${LASTEXITCODE}: $LgpoExe $lgpoArgs"
                    }
                    Write-Verbose -Verbose "Parsed '$item' to '$polText'"
                }
                else {
                    Write-Warning "Unable to determine machine vs user: '$item'"
                }
            }
        }
        else {
            Write-Warning "Unexpected file:`t$relPath"
        }
    }
}

foreach ($item in $didWeSeeTheseExpectedFiles.GetEnumerator()) {
    $relPath = $item.Key
    $seen = $item.Value
    if (-not $seen) {
        Write-Warning "Did not see expected file: '$relPath'"
    }
}
