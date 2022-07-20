#Requires -Version 5

<#
.SYNOPSIS
    Generates Event Viewer custom view files from a CSV file.
#>

param (
    [Parameter(Mandatory)]    
    [string]$CSVFile
)


Set-Variable -Option Constant -Name InvalidFileNameCharsRegex `
    -Value ('[{0}]' -f [RegEx]::Escape(([IO.Path]::GetInvalidFileNameChars() -join '')))

# These values need to match the CSV headings
Set-Variable -Option Constant -Name CategoryHeading -Value 'Audit Event Category'
Set-Variable -Option Constant -Name CriticalityHeading -Value 'Potential Criticality'
Set-Variable -Option Constant -Name EventIdHeading -Value 'Current Windows Event ID'

# XML template strings
Set-Variable -Option Constant -Name ViewerConfigTemplate -Value @'
<ViewerConfig>
    <QueryConfig>
        <QueryParams>
            <Simple>
                <Channel>PLACEHOLDER</Channel>
                <EventId>PLACEHOLDER</EventId>
                <RelativeTimeInfo>0</RelativeTimeInfo>
                <BySource>False</BySource>
            </Simple>
        </QueryParams>
        <QueryNode>
            <Name>PLACEHOLDER</Name>
            <QueryList>
                <Query Id="0" Path="PLACEHOLDER">
                    <Select Path="PLACEHOLDER">PLACEHOLDER</Select>
                </Query>
            </QueryList>
        </QueryNode>
    </QueryConfig>
</ViewerConfig>
'@
Set-Variable -Option Constant -Name SelectExpressionFormat -Value '*[System[({0})]]'
Set-Variable -Option Constant -Name SelectConjunction -Value ' or '
Set-Variable -Option Constant -Name SelectTermFormat -Value 'EventID={0}'


function New-EventViewerConfigXml {
    [CmdletBinding()]
    [OutputType([xml])]
    param (
        [string]
        $Name,

        [int[]]
        $EventIdList,

        [string]
        $ChannelPath = 'Security'
    )

    $IntegerEventIDList = $EventIDList | ForEach-Object { [int]$_ }
    $SortedEventIDList = $IntegerEventIDList | Sort-Object -Unique

    $SelectTermList = $SortedEventIDList | ForEach-Object { $SelectTermFormat -f $_ }
    $SelectTermText = $SelectTermList -join $SelectConjunction
    $SelectText = $SelectExpressionFormat -f $SelectTermText

    [xml]$x = $ViewerConfigTemplate

    $Simple = $x.ViewerConfig.QueryConfig.QueryParams.Simple
    $Simple.Channel = $ChannelPath
    $Simple.EventId = $SortedEventIDList -join ','

    $QueryNode = $x.ViewerConfig.QueryConfig.QueryNode
    $QueryNode.Name = $Name

    $Query0 = $QueryNode.QueryList.Query
    $Query0.Path = $ChannelPath

    $Select = $Query0.Select
    $Select.Path = $ChannelPath
    $Select.InnerText = $SelectText

    return $x
}


$OutFolder = Join-Path -Path $PSScriptRoot -ChildPath 'out'
if (-not (Test-Path -PathType Container -LiteralPath $OutFolder)) {
    New-Item -ItemType Directory -Path $OutFolder -Verbose | Out-Null
}

$Data = Import-Csv -Path $CSVFile

$CategoryGroups = @{}
foreach ($EventRecord in $Data) {
    $EventId = $EventRecord.$EventIdHeading -as [int]
    if (-not $EventId) { continue }

    $CategoryNames = -split $EventRecord.$CategoryHeading `
    | ForEach-Object { $_.ToLower() -replace ',', '' } `
    | Where-Object { $_ } `
    | Get-Unique -AsString
    
    foreach ($CategoryName in $CategoryNames) {
        if (-not $CategoryGroups.ContainsKey($CategoryName)) {
            $CategoryGroups[$CategoryName] = [System.Collections.Generic.List[string]]::new()
        }
        $CategoryGroups[$CategoryName].Add($EventId)
    }
}

foreach ($CategoryName in $CategoryGroups.Keys) {
    $CleanedName = $CategoryName -replace $InvalidFileNameCharsRegex, '_'
    $OutXMLName = 'ViewerConfig ' + $CleanedName + ".xml"
    $OutXMLFile = Join-Path -Path $OutFolder -ChildPath $OutXMLName

    $EventIdList = $CategoryGroups[$CategoryName]
    
    $ViewerConfigXml = New-EventViewerConfigXml -Name $CategoryName -EventIdList $EventIdList
    $ViewerConfigXml.Save($OutXMLFile)
}
