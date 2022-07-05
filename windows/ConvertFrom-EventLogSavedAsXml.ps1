[CmdletBinding()]
param (
    [Parameter(Mandatory = $true,
        Position = 0,
        ParameterSetName = "LiteralPath",
        ValueFromPipelineByPropertyName = $true,
        HelpMessage = "Literal path to saved XML file.")]
    [Alias("PSPath")]
    [ValidateNotNullOrEmpty()]
    [string[]]
    $LiteralPath
)

$ErrorActionPreference = 'Stop'

$ResolvedPath = Resolve-Path -LiteralPath $LiteralPath
[xml]$XmlData = ''

Write-Progress -Activity 'Loading XML'
$StopWatch = [System.Diagnostics.Stopwatch]::StartNew()
$XmlData.Load($ResolvedPath)
$StopWatch.Stop()
Write-Warning ".. $($StopWatch.Elapsed.TotalSeconds)  Loaded XML"

$StopWatch.Restart()
$n = $XmlData.Events.Event.Count
Write-Warning ".. ${n} events to convert"
$i = 0
foreach ($Event in $XmlData.Events.Event) {
    if ($i % 100 -eq 0) {
        Write-Progress -Activity 'Converting events' -PercentComplete (100 * $i / $n)
    }
    $i++
    
    try {
        $TimeCreated = [datetime]$Event.System.TimeCreated.SystemTime
        $Computer = $Event.System.Computer
        $Channel = $Event.System.Channel            # Security
        $EventID = [int]$Event.System.EventID
        $Level = $Event.RenderingInfo.Level         # Information
        $Provider = $Event.System.Provider.Name     # Microsoft-Windows-Security-Auditing
        $Task = $Event.RenderingInfo.Task           # Process Termination
        $Keyword = $Event.RenderingInfo.Keywords.Keyword
        if ($Keyword -isnot [string]) {
            $Keyword = $Event.RenderingInfo.Keywords.InnerXml
        }
        $Detail = $Event.RenderingInfo.Message
        $Message = $Detail -split "`n" | Select-Object -First 1

        $h = [ordered]@{
            TimeCreated = $TimeCreated
            Computer    = $Computer
            Channel     = $Channel
            EventID     = $EventID
            Level       = $Level
            Provider    = $Provider
            Task        = $Task
            Keyword     = $Keyword
            Message     = $Message
            Detail      = $Detail
        }
        foreach ($Data in $Event.EventData.Data) {
            $Name = $Data.Name                          # SubjectUserSid
            $Text = $Data.InnerXml                      # S-1-5-18
            $h[$Name] = $Text
        }
        [PSCustomObject]$h
    }
    catch {
        Write-Warning "** ${i} ${EventID} $($Event.OuterXml)"
        throw
    }
}
$StopWatch.Stop()
Write-Warning ".. $($StopWatch.Elapsed.TotalSeconds)  Converted events"
