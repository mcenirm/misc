[CmdletBinding()]
param (
    [Parameter(Mandatory = $true,
        Position = 0,
        ParameterSetName = "Path",
        ValueFromPipeline = $true,
        ValueFromPipelineByPropertyName = $true,
        HelpMessage = "Path to one or more CSV files.")]
    [ValidateNotNullOrEmpty()]
    [SupportsWildcards()]
    [string[]]
    $Path,

    [string]
    $Sep = '_',

    [string]
    $Missing = 'N/A'
)


# TODO include LastWriteTime


function Extract-NameAndSerial {
    param(
        [System.IO.FileInfo]
        $File,
        [string]
        $Sep
    )

    $Parts = $File.BaseName -split $Sep
    if ($Parts.Length -gt 1) {
        $Serial = $Parts[-1]
        $Name = $Parts[0..($Parts.Length - 2)] -join $Sep
    }
    else {
        $Serial = $null
        $Name = $File.BaseName
    }
    return @{ Name = $Name; Serial = $Serial }
}


$Path | ForEach-Object {
    $File = [System.IO.FileInfo]$_
    $NameAndSerial = Extract-NameAndSerial -File $File -Sep $Sep
}







$PrefixHeader = "Name,Serial,"

$Header = $null
$HeaderFrom = $null

$Path | Get-ChildItem | ForEach-Object {
    $File = $_
    $NameParts = $File.BaseName -split $Sep
    if ($NameParts.Count -gt 1) {
        $Serial = $NameParts[-1]
        $FixedName = $NameParts[0..($NameParts.Count - 2)] -join $Sep
        $Prefix = ($FixedName, $Serial | ForEach-Object { '"' + ( $_ -replace '"', '""') + '",' }) -join ''
    }
    else {
        $Serial = $null 
        $FixedName = $_.BaseName
        $Prefix = ($FixedName, 'N/A' | ForEach-Object { '"' + ( $_ -replace '"', '""') + '",' }) -join ''
    }
    $i = 0
    Get-Content -LiteralPath $File | ForEach-Object {
        $Line = $_
        if ($i -eq 0) {
            if ($null -ne $Header) {
                if ($Line -ne $Header) {
                    Write-Warning "Mismatched headers: $HeaderFrom vs $File"
                }
            }
            else {
                $Header = $Line
                $HeaderFrom = $File
                Write-Output "$PrefixHeader$Line"
            }
        }
        else {
            Write-Output "$Prefix$Line"
        }
        $i++
    }
}
