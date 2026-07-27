# DOES NOT WORK WITH PAGEANT YET
# TODO keep listening after client closes

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [System.Net.IPAddress]$ListenAddress = [System.Net.IPAddress]::Loopback,

    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 65535)]
    [int]$TcpPort = 7625,

    [Parameter(Mandatory = $false)]
    [ValidateNotNullOrEmpty()]
    [string]$PipeName = "pageant.${env:USERNAME}.*",

    [Parameter(Mandatory = $false)]
    [ValidateRange(100, 60000)]
    [int]$ConnectTimeoutMs = 5000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([System.Management.Automation.WildcardPattern]::ContainsWildcardCharacters($PipeName)) {
    Write-Host "original: `t$PipeName"
    # Support simple wildcards
    if ($PipeName -notmatch '[\\/]') {
        $PipeName = "\\.\pipe\$PipeName"
    }
    Write-Host "fixed: `t$PipeName"

    # Replace pipe wildcard with first match that is live
    $Win32 = Add-Type -Name 'NamedPipeUtils' -Namespace 'Win32' -PassThru -MemberDefinition @'
[DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
public static extern bool WaitNamedPipe(string lpNamedPipeName, uint nTimeOut);
'@
    $firstLive = $null
    foreach ($test in (Get-Item -Path $PipeName)) {
        # Timeout = 0 checks immediate availability without waiting or opening
        $timeout = 0
        if ($Win32::WaitNamedPipe($test.FullName, $timeout)) {
            Write-Host "testing: `t$($test.FullName)"
            $firstLive = $test
            break
        }
    }
    Write-Host "worked?: `t$($null -ne $firstLive)"
    if ($null -eq $firstLive) {
        Write-Error "Unable to find live pipe with wildcard: $PipeName" -ErrorAction Stop
    }
    $PipeName = $firstLive
}
Write-Host "using: `t$PipeName"

try {
    $tcpListener = [System.Net.Sockets.TcpListener]::new($ListenAddress, $TcpPort)
    $tcpListener.Start()
    Write-Host "TCP Listener started on ${ListenAddress}:${TcpPort}. Waiting for incoming connection..."

    $tcpClient = $tcpListener.AcceptTcpClient()
    $tcpStream = $tcpClient.GetStream()
    Write-Host "TCP Client connected from $($tcpClient.Client.RemoteEndPoint)."

    $pipeClient = [System.IO.Pipes.NamedPipeClientStream]::new(
        ".",
        $PipeName,
        [System.IO.Pipes.PipeDirection]::InOut,
        [System.IO.Pipes.PipeOptions]::Asynchronous
    )

    try {
        Write-Host "Connecting to Named Pipe: \\.\pipe\$PipeName ..."
        $pipeClient.Connect($ConnectTimeoutMs)
        Write-Host "Connected. Proxying traffic..."

        # Asynchronous bidirectional stream copy prevents CPU polling spikes
        # and avoids invalid .Length calls on non-seekable pipe streams
        $pipeToTcp = $pipeClient.CopyToAsync($tcpStream)
        $tcpToPipe = $tcpStream.CopyToAsync($pipeClient)

        [System.Threading.Tasks.Task]::WhenAny($pipeToTcp, $tcpToPipe).Wait()
    }
    catch {
        Write-Error "Proxy error: $_"
    }
    finally {
        if ($null -ne $pipeClient) { $pipeClient.Dispose() }
        if ($null -ne $tcpStream) { $tcpStream.Dispose() }
        if ($null -ne $tcpClient) { $tcpClient.Dispose() }
    }
}
finally {
    $tcpListener.Stop()
    Write-Host "Listener stopped and resources cleaned up."
}
