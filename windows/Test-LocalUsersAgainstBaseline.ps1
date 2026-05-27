
using module Microsoft.PowerShell.LocalAccounts
using namespace Microsoft.PowerShell.Commands
using namespace System.Collections.Generic
using namespace System.Linq
using namespace System.Security.Principal


[CmdletBinding()]
param (
    [Parameter(Mandatory)]
    [string]
    $BaselineUsersCsvPath
)


if (-not (Test-Path $BaselineUsersCsvPath)) {
    Write-Warning @"
The baseline users CSV file '$BaselineUsersCsvPath' should have contents similar to:
----------
"Name","FullName","Groups"
"reda","Alice Red","Lancers; Users"
"greenb","Bob Green","Lancers; Users"
"heal-greenb","Bob Green (healer)","Healers; Users"
"prot-yellowc","Carol Yellow (protection)","Tanks; Users"
"blued","Dan Blue","Lancers; Users"
"orangee","Eve Orange","Lancers; Users"
"heal-purplef","Frank Purple (healer)","Healers; Users"
"prot-purplef","Frank Purple (protection)","Tanks; Users"
"admin-grayg","Grace Gray (admin)","Administrators; Admins"
"backup-grayg","Grace Gray (backup)","Backup Operators; Users"
"heal-grayg","Grace Gray (healer)","Healers; Users"
----------
"@
    Write-Error "Could not find baseline users CSV file: ${BaselineUsersCsvPath}" -ErrorAction Stop
}

$BaselineData = Import-Csv -Path $BaselineUsersCsvPath -ErrorAction Stop


class BaselineUser {
    [string]$Name = ''
    [string]$FullName = ''
    [SortedSet[string]]$Groups = [SortedSet[string]]::new()
}


class LocalUserNameComparer : Comparer[LocalUser] {
    [int] Compare([LocalUser]$x, [LocalUser]$y) {
        if ($null -eq $x -and $null -eq $y) { return 0 }
        if ($null -eq $x) { return -1 }
        if ($null -eq $y) { return 1 }
        return [string]::Compare($x.Name, $y.Name, [StringComparison]::OrdinalIgnoreCase)
    }
}
class LocalGroupNameComparer : Comparer[LocalGroup] {
    [int] Compare([LocalGroup]$x, [LocalGroup]$y) {
        if ($null -eq $x -and $null -eq $y) { return 0 }
        if ($null -eq $x) { return -1 }
        if ($null -eq $y) { return 1 }
        return [string]::Compare($x.Name, $y.Name, [StringComparison]::OrdinalIgnoreCase)
    }
}
class LocalUserSet : SortedSet[LocalUser] {
    LocalUserSet () : base([LocalUserNameComparer]::new()) {}

    [SortedDictionary[string, LocalUser]]ByName() {
        $thisByName = [SortedDictionary[string, LocalUser]]::new()
        $this | ForEach-Object { $thisByName.Add($_.Name, $_) }
        return $thisByName
    }
}
class LocalGroupSet : SortedSet[LocalGroup] {
    LocalGroupSet () : base([LocalGroupNameComparer]::new()) {}

    [SortedDictionary[string, LocalGroup]]ByName() {
        $thisByName = [SortedDictionary[string, LocalGroup]]::new()
        $this | ForEach-Object { $thisByName.Add($_.Name, $_) }
        return $thisByName
    }
}
class GroupMembersDictionary : SortedDictionary[LocalGroup, SortedSet[LocalUser]] {
    GroupMembersDictionary () : base(
        [SortedDictionary[LocalGroup, [SortedSet[LocalUser]]]]::new(),
        [LocalGroupNameComparer]::new()
    ) {}
}


class FixesNeeded {
    $MissingUsers = [LocalUserSet]::new()
    $UnexpectedUsers = [LocalUserSet]::new()
    $FixUserFullNames = [LocalUserSet]::new()
    $MissingGroups = [LocalGroupSet]::new()
    $UnexpectedGroups = [LocalGroupSet]::new()
    $MissingGroupMembers = [GroupMembersDictionary]::new()
    $UnexpectedGroupMembers = [GroupMembersDictionary]::new()

    AddUserIsMissing([LocalUser]$missingUser) {
        $this.MissingUsers.Add($missingUser) | Out-Null
    }

    AddUserIsUnexpected([LocalUser]$unexpectedUser) {
        $this.UnexpectedUsers.Add($unexpectedUser) | Out-Null
    }

    AddUserHasIncorrectFullName([LocalUser]$userWithCorrectFullName) {
        $this.FixUserFullNames.Add($userWithCorrectFullName) | Out-Null
    }

    AddGroupIsMissing([LocalGroup]$missingGroup) {
        $this.MissingGroups.Add($missingGroup) | Out-Null
    }

    AddGroupIsUnexpected([LocalGroup]$unexpectedGroup) {
        $this.UnexpectedGroups.Add($unexpectedGroup) | Out-Null
    }

    AddUserIsNotInGroup([LocalUser]$user, [LocalGroup]$group) {
        if (-not $this.MissingGroupMembers.ContainsKey($group)) {
            $this.MissingGroupMembers.Add($group, [LocalUserSet]::new())
        }
        $this.MissingGroupMembers[$group].Add($user) | Out-Null
    }

    AddGroupMemberIsUnexpected([LocalGroup]$group, [LocalUser]$member) {
        if (-not $this.UnexpectedGroupMembers.ContainsKey($group)) {
            $this.UnexpectedGroupMembers.Add($group, [LocalUserSet]::new())
        }
        $this.UnexpectedGroupMembers[$group].Add($member) | Out-Null
    }

}


class UsersAndGroups {
    $users = [LocalUserSet]::new()
    $groups = [LocalGroupSet]::new()
    $userNameToGroupNames = [SortedDictionary[string, SortedSet[string]]]::new()

    AddGroup([LocalGroup]$Group) {
        if (-not $this.groups.Add($Group)) {
            [LocalGroup]$oldGroup = $null
            if ($this.groups.TryGetValue($Group, [ref]$oldGroup)) {
                $oldJson, $newJson = $oldGroup, $Group | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 1 }
                if ($oldJson -ne $newJson) {
                    Write-Error "group mismatch: $_`n$oldJson`nvs`n$newJson" -ErrorAction Stop
                }
            }
            else {
                # this should be a logic error, but ¯\_(ツ)_/¯
            }
        }
    }

    AddUser([LocalUser]$User, [LocalGroup[]]$Groups) {
        if (-not $this.users.Add($User)) {
            [LocalUser]$oldUser = $null
            if ($this.users.TryGetValue($User, [ref]$oldUser)) {
                $oldJson, $newJson = $oldUser, $User | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 1 }
                if ($oldJson -ne $newJson) {
                    Write-Error "user mismatch: $_`n$oldJson`nvs`n$newJson" -ErrorAction Stop
                }
            }
            else {
                # this should be a logic error, but ¯\_(ツ)_/¯
            }
        }
        $newGroupNames = [SortedSet[string]]::new()
        if ($Groups.Count -gt 0) {
            $newGroupNames.UnionWith([string[]]$Groups.Name)
        }
        $oldGroupNames = $this.userNameToGroupNames[$User.Name]
        if ($null -eq $oldGroupNames) {
            $this.userNameToGroupNames[$User.Name] = $newGroupNames
        }
        elseif (-not $newGroupNames.SetEquals($oldGroupNames)) {
            $oldJson, $newJson = $oldGroupNames, $newGroupNames | ConvertTo-Json -Compress -depth 1
            Write-Error "groups mismatch for user $($User.Name): $_`n$oldJson`nvs`n$newJson" -ErrorAction Stop
        }
        $Groups | ForEach-Object { $this.AddGroup($_) }
    }

    [FixesNeeded]DeviationFromBaseline([UsersAndGroups]$Baseline) {
        $f = [FixesNeeded]::new()

        $thisUsersByName = $this.users.ByName()
        $thisGroupsByName = $this.groups.ByName()
        $baselineUsersByName = $Baseline.users.ByName()
        $baselineGroupsByName = $Baseline.groups.ByName()

        $unexpectedGroupNames = [Enumerable]::Except($thisGroupsByName.Keys, $baselineGroupsByName.Keys)
        $missingGroupNames = [Enumerable]::Except($baselineGroupsByName.Keys, $thisGroupsByName.Keys)
        $unexpectedUserNames = [Enumerable]::Except($thisUsersByName.Keys, $baselineUsersByName.Keys)
        $missingUserNames = [Enumerable]::Except($baselineUsersByName.Keys, $thisUsersByName.Keys)
        $intersectUserNames = [Enumerable]::Intersect($thisUsersByName.Keys, $baselineUsersByName.Keys)
        $intersectGroupNames = [Enumerable]::Intersect($thisGroupsByName.Keys, $baselineGroupsByName.Keys)

        # unexpected groups: in this but not in baseline
        foreach ($unexpectedGroupName in $unexpectedGroupNames) {
            $unexpectedGroup = $thisGroupsByName[$unexpectedGroupName]
            $sid = $unexpectedGroup.SID.Value
            if ($null -ne $sid -and - $sid.StartsWith('S-1-5-32-')) {
                # do not treat NT builtin groups as unexpected
            }
            else {
                $f.AddGroupIsUnexpected($unexpectedGroup)
            }
        }

        # missing groups: in baseline but not in this
        foreach ($missingGroupName in $missingGroupNames) {
            $missingGroup = $baselineGroupsByName[$missingGroupName]
            $f.AddGroupIsMissing($missingGroup)
        }

        # unexpected users: in this but not in baseline
        foreach ($unexpectedUserName in $unexpectedUserNames) {
            $unexpectedUser = $thisUsersByName[$unexpectedUserName]
            $f.AddUserIsUnexpected($unexpectedUser)
        }

        # missing users: in baseline but not in this
        foreach ($missingUserName in $missingUserNames) {
            $missingUser = $baselineUsersByName[$missingUserName]
            $f.AddUserIsMissing($missingUser)
            $namesOfGroupsThatUserIsNotIn = $Baseline.userNameToGroupNames[$missingUser.Name]
            foreach ($groupName in $namesOfGroupsThatUserIsNotIn) {
                [LocalGroup]$groupThatUserIsNotIn = $baselineGroupsByName[$groupName]
                $f.AddUserIsNotInGroup($missingUser, $groupThatUserIsNotIn)
            }
        }

        # mismatched users: in this and in baseline, but something is wrong
        foreach ($userName in $intersectUserNames) {
            [LocalUser]$thisUser = $thisUsersByName[$userName]
            [LocalUser]$baselineUser = $baselineUsersByName[$userName]
            if ($thisUser.FullName -ne $baselineUser.FullName) {
                $f.AddUserHasIncorrectFullName($baselineUser)
            }

            $thisGroupNames = $this.userNameToGroupNames[$userName]
            $baselineGroupNames = $Baseline.userNameToGroupNames[$userName]
            foreach ($groupName in [Enumerable]::Except($thisGroupNames, $baselineGroupNames)) {
                [LocalGroup]$unexpectedGroup = $thisGroupsByName[$groupName]
                $f.AddGroupMemberIsUnexpected($unexpectedGroup, $thisUser)
            }
            foreach ($groupName in [Enumerable]::Except($baselineGroupNames, $thisGroupNames)) {
                [LocalGroup]$missingGroup = $baselineGroupsByName[$groupName]
                $f.AddUserIsNotInGroup($baselineUser, $missingGroup)
            }
        }

        # mismatched groups: in this and in baseline, but something is wrong
        foreach ($groupName in $intersectGroupNames) {
            # [LocalGroup]$thisGroup = $thisGroupsByName[$groupName]
            [LocalGroup]$baselineGroup = $baselineGroupsByName[$groupName]

            # unexpected group members: this group has a member that does not match baseline
            foreach ($thisUser in $this.users) {
                if ($this.userNameToGroupNames[$thisUser.Name].Contains($groupName)) {
                    [LocalUser]$baselineUser = $baselineUsersByName[$thisUser.Name]
                    if ($null -eq $baselineUser) {
                        # user is in this, but not in baseline
                        $f.AddGroupMemberIsUnexpected($baselineGroup, $thisUser)
                    }
                    elseif ($Baseline.userNameToGroupNames[$baselineUser.Name].Contains($groupName)) {
                        # user is in expected group, so no action
                    }
                    else {
                        $f.AddGroupMemberIsUnexpected($baselineGroup, $baselineUser)
                    }
                }
            }
        }

        return $f
    }
}


function New-BaselineUsersAndGroups {
    [CmdletBinding()]
    [OutputType([UsersAndGroups])]
    param (
        [BaselineUser[]]
        $Users
    )

    $buag = [UsersAndGroups]::new()
    foreach ($user in $Users) {
        if ($user.Name -eq '--') {
            # TODO handle rows with only group names ??
        }
        else {
            $luser = [LocalUser]::new($user.Name)
            $luser.FullName = $user.FullName
            $buag.AddUser($luser, ($user.Groups | ForEach-Object { [LocalGroup]::new($_) }))
        }
    }
    return $buag
}


function New-ExistingUsersAndGroups {
    [CmdletBinding()]
    [OutputType([UsersAndGroups])]
    param()

    $euag = [UsersAndGroups]::new()
    $users = Get-LocalUser
    $groups = Get-LocalGroup
    $usersBySid = [SortedDictionary[SecurityIdentifier, LocalUser]]::new()
    $membersByGroupName = [SortedDictionary[string, List[LocalPrincipal]]]::new()
    $groupsByUserName = [SortedDictionary[string, List[LocalGroup]]]::new()
    foreach ($u in $users) {
        $usersBySid.Add($u.SID, $u)
        $groupsByUserName.Add($u.Name, [List[LocalGroup]]::new())
    }
    foreach ($g in $groups) {
        $members = Get-LocalGroupMember -Group $g
        $membersByGroupName.Add($g.Name, $members)
        foreach ($m in $members) {
            if ($usersBySid.ContainsKey($m.SID)) {
                $u = $usersBySid[$m.SID]
                $groupsByUserName[$u.Name].Add($g) | Out-Null
            }
        }
    }
    foreach ($u in $users) {
        [int]$rid = ($u.SID.Value -split '-')[-1]
        if ($rid -ge 1000) {
            $euag.AddUser($u, $groupsByUserName[$u.Name])
        }
    }
    foreach ($g in $groups) {
        $euag.AddGroup($g)
    }
    return $euag
}


[BaselineUser[]]$Users = $BaselineData | Select-Object Name, FullName, @{n = 'Groups'; e = { $_.Groups -split '; ' } }
$BaselineUsersAndGroups = New-BaselineUsersAndGroups $Users

$ExistingUsersAndGroups = New-ExistingUsersAndGroups

$Deviations = $ExistingUsersAndGroups.DeviationFromBaseline($BaselineUsersAndGroups)

'## Missing users'
$Deviations.MissingUsers | Format-Table Name, FullName
'## Unexpected users'
$Deviations.UnexpectedUsers | Format-Table Name, FullName
'## Fix user full names'
$Deviations.FixUserFullNames | Format-Table Name, FullName
'## Missing groups'
$Deviations.MissingGroups | Format-Table Name
'## Unexpected groups'
$Deviations.UnexpectedGroups | Format-Table Name
'## Missing group members'
$Deviations.MissingGroupMembers | Format-Table @{l = 'Name'; e = { $_.Key } }, @{l = 'Members'; e = { $_.Value -join ', ' } }
'## Unexpected group members'
$Deviations.UnexpectedGroupMembers | Format-Table @{l = 'Name'; e = { $_.Key } }, @{l = 'Members'; e = { $_.Value -join ', ' } }

# TODO Produce commands?
