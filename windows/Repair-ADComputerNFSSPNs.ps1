#Requires -Modules ActiveDirectory
[CmdletBinding()]
param (
    [Parameter(
        Mandatory = $true,
        Position = 0,
        ValueFromPipeline = $true
    )]
    [Microsoft.ActiveDirectory.Management.ADComputer]$Identity,

    [Parameter(Mandatory = $false)]
    [ValidateSet('NFSServer', 'NFSClient')]
    [string]$Role = 'NFSServer',

    [Parameter(Mandatory = $false)]
    [string]$OutputKeytab,

    [Parameter(Mandatory = $false)]
    [System.Management.Automation.PSCredential]$Credential
)


# WORK IN PROGRESS

# Decisions
#  * Should this be on the computer object? Should we create a dedicate service account user object?
#  * What needs to happen to the userPrincipalName?
#  * How many servicePrincipalName values are needed?
#    - nfs/<SHORTNAME>
#    - nfs/<FQDN>
#    - nfs/<SHORTNAME>@<REALM>
#    - nfs/<FQDN>@<REALM>
#  * What difference is there in NFS SPNs for role NFSServer vs role NFSClient?

# https://www.reddit.com/r/synology/comments/ttb20h/howto_synology_with_kerberized_nfs_and_redhat/
# https://kb.synology.com/en-us/DSM/tutorial/how_to_set_up_kerberized_NFS
# https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/ktpass
# https://wiki.samba.org/index.php/Generating_Keytabs
# https://fjordtek.com/categories/news/2021/kerberos-secured-network-file-shares-practical-guide-for-kerberized-nfsv4/
# https://access.redhat.com/solutions/6972993


Begin {
    $krbServicePrefix = 'nfs/'
    $servicePattern = "^$krbServicePrefix"
    $adargs = @{
        Verbose = $PSCmdlet.MyInvocation.BoundParameters["Verbose"].IsPresent -eq $true
    }
    if ($null -ne $Credential) {
        $adargs.Credential = $Credential
    }
}

Process {
    # Remove any NFS SPNs
    $computer = Get-ADComputer -Identity $Identity @adargs -Properties ServicePrincipalNames
    # [System.Management.Automation.PSSerializer]::Serialize($computer)
    $nfsspns = [System.Collections.ArrayList]::new()
    foreach ($spn in $computer.ServicePrincipalNames) {
        if ($spn -match $servicePattern) {
            [void]$nfsspns.Add($spn)
        }
    }
    if ($nfsspns.Count -gt 0) {
        Set-ADComputer -Identity $computer @adargs -ServicePrincipalNames @{
            Remove = [array]$nfsspns
        }
    }
    # [System.Management.Automation.PSSerializer]::Serialize($computer)

    # TODO Initialize ktpass using first desired NFS SPN
    # TODO Add each remaining NFS SPN to ktpass
}

End {
}
