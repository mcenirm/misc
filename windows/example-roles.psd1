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
