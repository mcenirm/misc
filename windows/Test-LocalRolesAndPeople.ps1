$DataFileName = 'LocalRolesAndPeople.psd1'

$DataPath = $null
foreach ($d in $PWD, $PSScriptRoot) {
    $p = Join-Path -Path $d -ChildPath $DataFileName
    if (Test-Path -LiteralPath $p) {
        $DataPath = $p
        break
    }
}
if ($null -eq $DataPath) {
    Write-Warning @"
The data file '${DataFileName}' should have contents similar to:
----------
@{
    Roles  = @{
        Regular = @{
            Groups         = @(
                'Users'
                'Project A'
            )
            UserNamePrefix = ''
            FullNameSuffix = ''
        }
        Admin   = @{
            Groups         = @(
                'Administrators'
            )
            UserNamePrefix = 'admin-'
            FullNameSuffix = ' (admin)'
        }
    }
    People = @{
        jonesj = @{
            Roles    = @(
                'Admin'
                'Backup'
            )
            FullName = 'Jane Jones'
        }
        smithj = @{
            Roles    = @(
                'Regular'
                'Audit'
            )
            FullName = 'John Smith'
        }
    }
}
----------
"@
    Write-Error "Could not find data file: ${DataFileName}" -ErrorAction Stop
}
$Data = Import-PowerShellDataFile -LiteralPath $DataPath

foreach ($Role in $Data.Roles.GetEnumerator()) {
    foreach ($GroupName in $Role.Groups) {
        $ExistingLocalGroup = Get-LocalGroup -Name $GroupName -ErrorAction SilentlyContinue
        if ($null -eq $ExistingLocalGroup) {
            Write-Output "New-LocalGroup -Name '${GroupName}' -Verbose"
        }
    }
}

$WrotePasswordCommand = $false
foreach ($Person in $Data.People.GetEnumerator()) {
    foreach ($RoleName in $Person.Value.Roles) {
        $Role = $Data.Roles[$RoleName]
        $UserName = $Role.UserNamePrefix + $Person.Key
        $FullName = $Person.Value.FullName + $Role.FullNameSuffix
        $ExistingLocalUser = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
        if ($null -eq $ExistingLocalUser) {
            if (-not $WrotePasswordCommand) {
                Write-Output @'
#
# Use one of the following commands to set the initial password.
#
# Manual:
#
#  $PasswordSecureString = Read-Host 'Enter password' -AsSecureString
#
# Unrecoverable random password:
#
#  $PasswordSecureString = [System.Web.Security.Membership]::GeneratePassword(16,4) | ConvertTo-SecureString -AsPlainText -Force
#
'@
                $WrotePasswordCommand = $true
            }
            Write-Output ''
            Write-Output "New-LocalUser           -Verbose -Name   '${UserName}' -FullName '${FullName}' -Password `$PasswordSecureString"
            foreach ($GroupName in $Role.Groups) {
                Write-Output "Add-LocalGroupMember    -Verbose -Member '${UserName}' -Group '${GroupName}'"
            }
        }
        else {
            $SetArgs = @{}
            if ($ExistingLocalUser.FullName -cne $FullName) {
                $SetArgs.FullName = $FullName
            }
            if ($SetArgs.Count -gt 0) {
                $SetCmd = "Set-LocalUser           -Verbose -Name   '${UserName}'"
                foreach ($SetArg in $SetArgs.GetEnumerator()) {
                    $SetCmd += " -$(${SetArg}.Key) '$(${SetArg}.Value.ToString())'"
                }
            }
            $NeedToRemoveUserFromGroups = @{}
            Get-LocalGroup | ForEach-Object {
                $Group = $_
                Get-LocalGroupMember -Group $Group | ForEach-Object {
                    $Member = $_
                    if ($Member.SID -eq $ExistingLocalUser.SID) {
                        $NeedToRemoveUserFromGroups[$Group.Name] = $true
                    }
                }
            }
            $NeedToAddUserToGroups = @{}
            foreach ($GroupName in $Role.Groups) {
                if ($NeedToRemoveUserFromGroups.ContainsKey($GroupName)) {
                    $NeedToRemoveUserFromGroups.Remove($GroupName)
                }
                else {
                    $NeedToAddUserToGroups[$GroupName] = $true
                }
            }
            if (($SetArgs.Count -gt 0) -or ($NeedToRemoveUserFromGroups.Count -gt 0) -or ($NeedToAddUserToGroups.Count -gt 0)) {
                Write-Output ''
            }
            if ($SetArgs.Count -gt 0) {
                Write-Output $SetCmd
            }
            foreach ($Group in $NeedToRemoveUserFromGroups.GetEnumerator()) {
                Write-Output "Remove-LocalGroupMember -Verbose -Member '${UserName}' -Name '$(${Group}.Key)'"
            }
            foreach ($Group in $NeedToAddUserToGroups.GetEnumerator()) {
                Write-Output "Add-LocalGroupMember    -Verbose -Member '${UserName}' -Name '$(${Group}.Key)'"
            }
        }
    }
}
