
using namespace System.Collections.Generic


[CmdletBinding()]
param (
    [Parameter(Mandatory)]
    [string]
    $PeopleCsvPath,

    [Parameter(Mandatory)]
    [string]
    $RolesDataPath
)


if (-not (Test-Path $RolesDataPath)) {
    Write-Warning @"
The roles data file '$RolesDataPath' should have contents similar to:
----------
@{
    Damage     = @{
        Groups         = @('Users', 'Lancers')
        UserNamePrefix = ''
        FullNameSuffix = ''
    }
    Protection = @{
        Groups         = @('Users', 'Tanks')
        UserNamePrefix = 'prot-'
        FullNameSuffix = ' (protection)'
    }
    Healing    = @{
        Groups         = @('Users', 'Healers')
        UserNamePrefix = 'heal-'
        FullNameSuffix = ' (healer)'
    }
    Admin      = @{
        Groups         = @('Administrators', 'Admins')
        UserNamePrefix = 'admin-'
        FullNameSuffix = ' (admin)'
        ImpliedRoles   = @('BackupOp')
    }
    BackupOp   = @{
        Groups         = @('Users', 'Backup Operators')
        UserNamePrefix = 'backup-'
        FullNameSuffix = ' (backup)'
        ImpliedRoles   = @('BackupOp')
    }
}
----------
"@
    Write-Error "Could not find roles data file: ${RolesDataPath}" -ErrorAction Stop
}
$RolesData = Import-PowerShellDataFile -LiteralPath $RolesDataPath -ErrorAction Stop


if (-not (Test-Path $PeopleCsvPath)) {
    Write-Warning @"
The people CSV file '$PeopleCsvPath' should have contents similar to:
----------
UserName,FullName,PrimaryRole,Healing
reda,Alice Red,Damage,FALSE
greenb,Bob Green,Damage,TRUE
yellowc,Carol Yellow,Protection,FALSE
blued,Dan Blue,Damage,FALSE
orangee,Eve Orange,Damage,FALSE
purplef,Frank Purple,Protection,TRUE
grayg,Grace Gray,Admin,TRUE
----------
"@
    Write-Error "Could not find people CSV file: ${PeopleCsvPath}" -ErrorAction Stop
}
$PeopleData = Import-Csv -Path $PeopleCsvPath -ErrorAction Stop


class RoleDefinition {
    $RoleName = ''
    $GroupNames = [SortedSet[string]]::new()
    $UserNamePrefix = ''
    $FullNameSuffix = ''
    $ImpliedRoleNames = [SortedSet[string]]::new()
}


class RoleDefinitionCollection {
    [SortedDictionary[string, RoleDefinition]]$Roles
    [SortedSet[string]]$GroupNames

    RoleDefinitionCollection([hashtable]$RolesData) {
        $this.Roles = [SortedDictionary[string, RoleDefinition]]::new()
        $this.GroupNames = [SortedSet[string]]::new()

        $unresolvedRoleNames = [SortedSet[string]]::new()

        foreach ($roleEntry in $RolesData.GetEnumerator()) {
            $roleName = $roleEntry.Key
            $role = $roleEntry.Value

            $def = [RoleDefinition]::new()
            $def.RoleName = $roleName
            if ($null -ne $role.Groups) {
                $def.GroupNames.UnionWith([string[]]$role.Groups)
                $this.GroupNames.UnionWith($def.GroupNames)
            }
            if ($null -ne $role.UserNamePrefix) {
                $def.UserNamePrefix = $role.UserNamePrefix
            }
            if ($null -ne $role.FullNameSuffix) {
                $def.FullNameSuffix = $role.FullNameSuffix
            }
            if ($null -ne $role.ImpliedRoles) {
                $def.ImpliedRoleNames.UnionWith([string[]]$role.ImpliedRoles)
                $unresolvedRoleNames.UnionWith($def.ImpliedRoleNames)
            }
            $this.Roles.Add($roleName, $def)
        }
        
        $unresolvedRoleNames.ExceptWith($this.Roles.Keys)
        if ($unresolvedRoleNames.Count -gt 0) {
            Write-Error "unresolved role names: $($unresolvedRoleNames -join ', ')" -ErrorAction Stop
        }
    }

    [List[RoleDefinition]] RecurseImpliedRoles([IEnumerable[string]]$RoleNames) {
        # start with what we're given
        $names = [SortedSet[string]]::new()
        $names.UnionWith($RoleNames)
        # ... and add them to the queue
        $q = [List[string]]::new()
        $q.AddRange($names)
        while ($q.Count -gt 0) {
            # pop the first name, and get the role def
            $n = $q[0]
            $q.RemoveAt(0)
            [RoleDefinition]$r = $this.Roles[$n]
            # get the implied roles and add them to the set of names
            $implieds = [SortedSet[string]]::new()
            $implieds.UnionWith($r.ImpliedRoleNames)
            $names.UnionWith($implieds)
            # subtract the ones we've already seen
            $implieds.ExceptWith($names)
            # and the leftovers to the queue
            $q.AddRange($implieds)
        }
        # return the named role defs
        $rv = [List[RoleDefinition]]::new()
        foreach ($n in $names) {
            $rv.Add($this.Roles[$n]) | Out-Null
        }
        return $rv
    }
}


class Person {
    $UserName = ''
    $FullName = ''
    $RoleNames = [SortedSet[string]]::new()
}


$RoleCollection = [RoleDefinitionCollection]::new($RolesData)

$People = $PeopleData | ForEach-Object {
    $row = $_
    $person = [Person]::new()
    foreach ($prop in $row.psobject.Properties) {
        $k = $prop.Name.Trim()
        $v = $prop.Value.Trim()
        try {
            # Try to assign based on class fields
            $person.$k = $v
        }
        catch {
            # Otherwise, assume role names
            switch ($k) {
                'Surname' { }
                'GivenName' { }
                { $k -eq 'PrimaryRole' } {
                    $person.RoleNames.Add($v) | Out-Null
                }
                { $v -eq 'TRUE' -or $v -eq $k } {
                    $person.RoleNames.Add($k) | Out-Null
                }
            }
        }
    }
    $person
}

$unresolvedRoleNames = [SortedSet[string]]::new()
foreach ($person in $People) {
    $unresolvedRoleNames.UnionWith($person.RoleNames)
}
$unresolvedRoleNames.ExceptWith($RoleCollection.Roles.Keys)
if ($unresolvedRoleNames.Count -gt 0) {
    Write-Error "unresolved role names: $($unresolvedRoleNames -join ', ')" -ErrorAction Stop
}

$unresolvedGroupNames = [SortedSet[string]]::new()
$unresolvedGroupNames.UnionWith($RoleCollection.GroupNames)
foreach ($person in $People) {
    $roleNames = ($RoleCollection.RecurseImpliedRoles($person.RoleNames)).RoleName
    foreach ($roleName in $roleNames) {
        $roleDef = $RoleCollection.Roles[$roleName]
        $userName = $roleDef.UserNamePrefix + $person.UserName
        $userFullName = $person.FullName + $roleDef.FullNameSuffix
        $groups = $roleDef.GroupNames -join '; '
        [pscustomobject]@{
            Name     = $userName
            FullName = $userFullName
            Groups   = $groups
        }
        $unresolvedGroupNames.ExceptWith($roleDef.GroupNames)
    }
}
foreach ($groupName in $unresolvedGroupNames) {
    [pscustomobject]@{
        Name     = '--'
        FullName = '--'
        Groups   = $groupName
    }
}
