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
        Audit   = @{
            Groups         = @(
                'Users',
                'Event Log Readers'
            )
            UserNamePrefix = 'audit-'
            FullNameSuffix = ' (audit)'
        }
        Backup  = @{
            Groups         = @(
                'Users',
                'Backup Operators'
            )
            UserNamePrefix = 'backup-'
            FullNameSuffix = ' (backup)'
        }
    }
    People = @{
        doej   = @{
            Roles    = @(
                'Admin'
                'Backup'
            )
            FullName = 'Jane Doe'
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
