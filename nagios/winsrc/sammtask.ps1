Switch($Action) {
    "Create-Task" {
        if ($ScriptPath -eq $null -or $ScriptName -eq $null -or `
                $Params -eq $null -or $TaskName -eq $null -or $TaskDescription -eq $null) {
            throw "Invalid Set of parameters. TaskName, TaskDescription, ScriptPath, ScriptName and Params are mandatory"
        }
        if ( -not (Test-Path "$ScriptPath\$ScriptName")) {
            throw "Script $ScriptPath\$ScriptName doesn't exist locally. Download first."
        }
        $trigger=new-scheduledtasktrigger -Once -At (Get-Date)
        $action=new-scheduledtaskaction -Execute "Powershell.exe" `
            -Argument "-NoProfile -WindowStyle Hidden -command $ScriptPath\$ScriptName $Params"

        Register-ScheduledTask -Action $action `
            -Trigger $trigger `
            -User $User `
            -Password $Password `
            -TaskName $TaskName `
            -TaskPath Samana `
            -Description $TaskDescription
    }
    "Delete-Task" {
        if($TaskName -eq $null) {
            throw "Invalid Set of parameters. TaskName is mandatory"            
        }
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath Samana
    }
    "Run-Task" {
        if($TaskName -eq $null) {
            throw "Invalid Set of parameters. TaskName is mandatory"            
        }
        $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        if ($t.State -ne "Ready") {
            throw "Task is not Ready. Current state is $($t.State)"
        }
        Start-ScheduledTask -TaskName $TaskName -TaskPath Samana
    }
    "List-Tasks" {
        Get-ScheduledTask -TaskPath \Samana
    }
    "Download-Script" {
        if($BaseUri -eq $null -or $ScriptPath -eq $null -or $ScriptName -eq $null) {
            throw "Invalid Set of parameters. BaseUri, ScriptPath and ScriptName are mandatory"            
        }
        if (-not (Test-Path $ScriptPath)) {
            New-Item $ScriptPath -ItemType Directory | Out-Null
        }
        Invoke-WebRequest -Uri "$BaseUri/$Scriptname" -OutFile "$ScriptPath\$ScriptName"
    }
    "Delete-Script" {
        if($ScriptPath -eq $null -or $ScriptName -eq $null) {
            throw "Invalid Set of parameters. ScriptPath and ScriptName are mandatory"            
        }
        Remove-Item $ScriptPath\$ScriptName -Recurse
    }
    "Cleanup" {
        if($ScriptPath -eq $null) {
            throw "Invalid Set of parameters. ScriptPath is mandatory"            
        }
        Clear-Item $ScriptPath
    }
    Default {
        throw "Invalid Action"
    }
}
