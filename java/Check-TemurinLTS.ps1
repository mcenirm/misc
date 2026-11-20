
$apiBaseUrl = 'https://api.adoptium.net/v3'
$availUrl = $apiBaseUrl + '/info/available_releases'
$releasesUrl = $apiBaseUrl + '/assets/feature_releases'

$ltsVersions = (Invoke-RestMethod -Uri $availUrl).available_lts_releases
foreach ($v in $ltsVersions) {
    $release = Invoke-RestMethod -Uri (
        @(
            @(
                $releasesUrl
                [System.Uri]::EscapeDataString($v)
                'ga'
            ) -join '/'
            (
                @{
                    os           = 'windows'
                    architecture = 'x64'
                    image_type   = 'jdk'
                    jvm_impl     = 'hotspot'
                    heap_size    = 'normal'
                    vendor       = 'eclipse'
                    page_size    = '1'
                }.GetEnumerator() | Sort-Object Key | ForEach-Object {
                    @(
                        [System.Uri]::EscapeDataString($_.Key)
                        [System.Uri]::EscapeDataString($_.Value)
                    ) -join '='
                }
            ) -join '&'
        ) -join '?'
    )
    [PSCustomObject]@{
        LTS          = $v
        ReleaseName  = $release[0].release_name
        BuildVersion = $release[0].version_data.semver
    }
}
