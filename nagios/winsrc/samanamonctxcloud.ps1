param(
    [Parameter(Mandatory)][string]$Action,
    [Parameter(Mandatory)][string]$XDCredentialsProfileName,
    [string]$EtcdServer,
    [string]$EtcdPort,
    [int]$MaxRecords=250,
    [int]$Ttl=360,
    [int]$DebugLevel=0,
    [Boolean]$Timing=$True,
    [string]$APIKey,
    [string]$CustomerId,
    [string]$SecretKey,
    [string]$BasePath="/samanamonitor/ctx_data",
    [string]$User,
    [string]$Password
)

if ( ($PSVersionTable).PSVersion -lt "5.1.0.0") {
    "Powershell version 5.1 or newer required. Aborting"
    return
}
asnp Citrix.Broker.Admin.V2
Add-Type -AssemblyName System.Web

Function UrlEncode {
    param([string]$s)
    return [System.web.HttpUtility]::UrlEncode($s)
}

class EtcdConnection {
    [string]$URI
    [string]$reqversion = "2.2.5"
    [PSObject]$version = @{}
    EtcdConnection([string]$URI) {
        $this.URI = $URI
        $this.version = $this.Send("GET", "$($this.URI)/version")
        if($this.version.etcdserver -ne $null -and $this.version.etcdserver -lt $this.reqversion) {
            throw "Invalid Etcd version $($this.version.etcdserver). Needed at least $($this.reqversion)"
        }
    }
    [PSObject]DownloadData([string]$Url) {
        $wc = New-Object net.webclient
        $wc.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT; Windows NT 10.0; en-US) WindowsPowerShell/5.1.14393.5127")
        $wc.Headers.Add("Content-Type", "application/x-www-form-urlencoded")
        try {
            $a=$wc.DownloadData($Url)
            $res = [System.Text.Encoding]::UTF8.GetString($a)
            $out = ConvertFrom-JSON $res
        } catch {
            if( $_.FullyQualifiedErrorId -eq "WebException" -and $_.Exception.InnerException.Response -ne $null) {
                $reader = New-Object System.IO.StreamReader($_.Exception.InnerException.Response.GetResponseStream())
                $out = ConvertFrom-JSON $reader.ReadToEnd()
            } else {
                $out = $_
            }
        }
        return $out
    }
    [PSObject]UploadData([string]$Method, [string]$Url, [System.Byte[]]$data) {
        $wc = New-Object net.webclient
        $wc.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT; Windows NT 10.0; en-US) WindowsPowerShell/5.1.14393.5127")
        $wc.Headers.Add("Content-Type", "application/x-www-form-urlencoded")
        try {
            $a=$wc.UploadData($Url, $Method, $data)
            $temp=[System.Text.Encoding]::UTF8.GetString($a)
            $out = ConvertFrom-JSON $temp
        } catch {
            if( $_.FullyQualifiedErrorId -eq "WebException" -and $_.Exception.InnerException.Response -ne $null) {
                $reader = New-Object System.IO.StreamReader($_.Exception.InnerException.Response.GetResponseStream())
                $out = ConvertFrom-JSON $reader.ReadToEnd()
            } else {
                $out = $_
            }
        }
        return $out
    }
    [PSObject]UploadData([string]$Method, [string]$Url, [PSObject]$Body) {
        $data = ""
        $Body.Keys | ForEach-Object {
            $val = UrlEncode("$($Body[$_])")
            $data += $_ + "=" + $val + "&"
        }
        return $this.UploadData($Method, $Url, [system.Text.Encoding]::UTF8.GetBytes($data))
    }

    [PSObject]Send([string]$Method, [string]$Uri) {
        if ($Method -ne "GET" -and $Method -ne "DELETE") {
            throw "Invalid Method"
        }
        Log -Level 5 -Message "Send start - $Method $Uri"
        if($Method -eq "GET") {
            $out = $this.DownloadData($Uri)
        } else {
            $out = $this.UploadData($Method, $Uri, [system.Text.Encoding]::UTF8.GetBytes(""))
        }
        Log -Level 5 -Message "Send end - $Method $Uri $out"
        return $out
    }
    [PSObject]Send([string]$Method, [string]$Uri, [PSObject]$Body) {
        Log -Level 5 -Message "Send start - $Method $Uri"
        $out = $null
        if($Method -eq "PUT") {
            $out = $this.UploadData($Method, $Uri, $Body)
        }
        Log -Level 5 -Message "Send end - $Method $Uri $out"
        return $out
    }
    [PSObject]Get([string]$Key) {
        return $this.Send("GET", "$($this.URI)/v2/keys$Key")
    }
    [PSObject]Rm([string]$Key) {
        return $this.Send("DELETE", "$($this.URI)/v2/keys$Key")
    }
    [PSObject]Set([string]$Key, [string]$Value) {
        return $this.Send("PUT", "$($this.URI)/v2/keys$Key",  @{value=$Value})
    }
    [PSObject]Set([string]$Key, [string]$Value, [int]$_TTL) {
        return $this.Send("PUT", "$($this.URI)/v2/keys$Key",   @{value=$Value; ttl=$_TTL})
    }
    [PSObject]MkDir([string]$Key) {
        return $this.Send("PUT", "$($this.URI)/v2/keys$Key",  @{dir=$True})
    }
    [PSObject]MkDir([string]$Key, [int]$_Ttl) {
        return $this.Send("PUT", "$($this.URI)/v2/keys$Key",  @{dir=$True; ttl=$_Ttl})
    }
    [PSObject]UpdateDir([string]$Key, [int]$Ttl) {
        $out = $this.Send("PUT", "$($this.URI)/v2/keys$Key", @{dir=$True; ttl=$Ttl; refresh=$True; prevExist=$True})
        if($out.errorCode -eq 100) {
            $out = $this.MkDir($Key, $Ttl)
        }
        return $out
    }
}

Function Save-State {
    param([bool]$Set, [PSObject]$Etcd, [string]$Path, $Value, [int]$Ttl)
    $current_state = $Etcd.Get($Path)
    if ($Set -and $current_state.node -eq $null) {
        return $Etcd.Set($Path, $Value, $Ttl)
    }
}

Function Log {
    param([int]$Level, [string]$Message)
    if ($DebugLevel -ge $Level) {
        $t = ""
        if ($Timing -and $Level -gt 0) {
            $t="$(Get-Date(Get-Date).ToUniversalTime()-uformat "%s") = "
        }  
        "$($t)$Message" | Write-Host
    }
}

Function Register-Machine {
    param(
        [string]$BasePath, 
        [PSObject]$Machine,
        [PSObject]$Etcd,
        [int]$Ttl)
    if($Ttl -lt 1) {
        throw "Invalid TTL"
    }
    Log -Level 3 -Message "Start Register-Machine $($Machine.DnsName)"
    $epoch = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
    $_ | Add-Member -NotePropertyName epoch -NotePropertyValue $epoch
    $_ | Add-Member -NotePropertyName Definitions -NotePropertyValue $definitions
    $value = $_ | ConvertTo-JSON -Compress
    $fqdn=$_.DnsName.ToLower()
    Log -Level 4 -Message "UpdateDir start $BasePath/machine/$fqdn"
    $temp = $Etcd.UpdateDir("$BasePath/machine/$fqdn", $Ttl*10)
    Log -Level 4 -Message "UpdateDir end $BasePath/machine/$fqdn"
    if ($_.DnsName -ne "" ) {
        Log -Level 4 -Message "Set Data start $BasePath/machine/$fqdn/data"
        $temp = $Etcd.Set("$BasePath/machine/$fqdn/data", $value, $Ttl)
        Log -Level 4 -Message "Set Data end $BasePath/machine/$fqdn/data $temp"

        Log -Level 4 -Message "Save state maintenance start $BasePath/machine/$fqdn/maintenance"
        $temp = Save-State -Set ($_.InMaintenanceMode) -Etcd $Etcd `
            -Path "$BasePath/machine/$fqdn/maintenance" -Value $epoch -Ttl $Ttl
        Log -Level 4 -Message "Save state maintenance end $BasePath/machine/$fqdn/maintenance $temp"

        Log -Level 4 -Message "Save state registered start $BasePath/machine/$fqdn/unregistered"
        $temp = Save-State -Set ($_.Registered -ne "Registered") -Etcd $Etcd `
            -Path "$BasePath/machine/$fqdn/unregistered" -Value $epoch -Ttl $Ttl
        Log -Level 4 -Message "Save state registered end $BasePath/machine/$fqdn/unregistered $temp"
    }
    Log -Level 4 -Message "UpdateDir start $BasePath/machine/$fqdn"
    $temp = $Etcd.UpdateDir("$BasePath/machine/$fqdn", $Ttl)
    Log -Level 4 -Message "UpdateDir end $BasePath/machine/$fqdn $temp"
    Log -Level 3 -Message "End Register-Machine $($Machine.DnsName)"
}

Function Create-Credentials {
    param(
        [string]$XDCredentialsProfileName,
        [string]$APIKey,
        [string]$CustomerId,
        [string]$SecretKey)
    return Set-XDCredentials -StoreAs $XDCredentialsProfileName -APIKey $APIKey -CustomerId $CustomerId -SecretKey $SecretKey -ProfileType CloudApi
}

Function Get-CitrixData {
    param(
        [Parameter(Mandatory)][string]$XDCredentialsProfileName,
        [Parameter(Mandatory)][string]$EtcdServer,
        [Parameter(Mandatory)][string]$EtcdPort
    )
    $StartTime=Get-Date(Get-Date).ToUniversalTime()-uformat "%s"
    Log -Level 1 -Message "Start"
    try {
        $e = [EtcdConnection]::new("http://$($EtcdServer):$($EtcdPort)")
    } catch {
        Log -Level 0 -Message "$_ -- http://$($EtcdServer):$($EtcdPort)"
        return
    }
    try {
        $p=Get-XDCredentials -ProfileName $XDCredentialsProfileName
        Get-XDAuthentication –ProfileName $XDCredentialsProfileName
    } catch {
        Log -Level 0 -Message "Credential Profile cannot be found. Aborting."
        return
    }
    $customerId=$p.Credentials.CustomerId
    $sitename=(Get-BrokerSite).Name

    $customerpath="$BasePath/$CustomerId"
    $sitepath="$customerpath/$SiteName"

    $lastuid=0
    $temp = $e.UpdateDir($customerpath, $ttl*10)
    $temp = $e.UpdateDir($sitepath, $ttl*10)
    $ctxtime = 0
    while($true) {
        $ctxstart=Get-Date(Get-Date).ToUniversalTime()-uformat "%s"
        $m=get-brokermachine -MaxRecordCount $MaxRecords -SortBy Uid -Filter {Uid -gt $lastUid}
        $ctxtime += (Get-Date(Get-Date).ToUniversalTime()-uformat "%s") - $ctxstart
        Log -Level 2 -Message "Page - $($m.Length)"
        if ($m.Length -eq 0 ) {
            break
        }
        $lastuid = $m[-1].Uid
        $m | ForEach {
            Register-Machine -BasePath $sitepath -Machine $_ -Etcd $e -Ttl $ttl
            Log -Level 3 -Message "$($_.DNSName)"
        }
    }
    $temp = $e.UpdateDir($customerpath, $ttl)
    $temp = $e.UpdateDir($sitepath, $ttl)
    Log -Level 1 -Message "End"
    $EndTime=Get-Date(Get-Date).ToUniversalTime()-uformat "%s"
    $exectime = [Math]::Round(($EndTime - $StartTime), 2)
    $ctxtime = [Math]::Round($ctxtime, 2)
    $e.Set("$sitepath/msg", "Path: $CustomerId/$SiteName | exectime=$($exectime);;;; ctxtime=$ctxtime;;;;", $ttl)
    Log -Level 0 -Message "Path: $CustomerId/$SiteName | exectime=$($exectime);;;; ctxtime=$ctxtime;;;;"
}

Function Create-Task {
    param(
        [string]$User,
        [string]$Password,
        [string]$XDCredentialsProfileName,
        [string]$EtcdServer,
        [string]$Etcdport,
        [string]$ScriptPath)
    $cmd = "$ScriptPath -XDCredentialsProfileName $XDCredentialsProfileName " `
        + "-EtcdServer $EtcdServer -EtcdPort $Etcdport"
    $trigger=new-scheduledtasktrigger -Once -At (Get-Date)
    $action=new-scheduledtaskaction -Execute "Powershell.exe" `
        -Argument "-NoProfile -WindowStyle Hidden -command $cmd"

    Register-ScheduledTask -Action $action `
        -Trigger $trigger `
        -User $User `
        -Password $Password `
        -TaskName "CtxDaasSamanaMon" `
        -Description "Citrix DaaS Samana Mon"
}

Function GetorCreate-Task {
    param(
        [string]$User,
        [string]$Password,
        [string]$XDCredentialsProfileName,
        [string]$EtcdServer, [string]$Etcdport,
        [string]$ScriptPath)
    try {
        $t = Get-ScheduledTask -TaskName CtxDaasSamanaMon -ErrorAction Stop
    } catch {
        Create-Task -ScriptPath $ScriptPath -User $User -Password $Password -`
            XDCredentialsProfileName $XDCredentialsProfileName -EtcdServer $EtcdServer `
            -Etcdport $Etcdport
        $t = Get-ScheduledTask -TaskName CtxDaasSamanaMon
    }
    return $t
}

Function Run-Task {
    param([PSObject]$Task)
    if ($task.State -eq "Ready") {
        "OK - Starting Process..." | Write-Host
        Start-ScheduledTask -TaskName CtxDaasSamanaMon
        return 0
    } elseif ($task.State -eq "Running") {
        "CRITICAL - Process still running... Waiting until next execution" | Write-Host
        return 3
    }
}


Switch($Action) {
    "Get-CitrixData" {
        if ($EtcdServer -eq $null -or $EtcdPort -eq $null) {
            Throw "EtcdServer and EtcdPort are mandatory parameters"
            return
        }
        Get-CitrixData -XDCredentialsProfileName $XDCredentialsProfileName -EtcdServer $EtcdServer -EtcdPort $EtcdPort
        "OK - Data Collected" | Write-Host
        return 0
    }
    "Create-Credentials" {
        if ($APIKey -eq $null -or $CustomerId -eq $null -or $SecretKey -eq $null) {
            Throw "APIKey, CustomerId and SecretKey are mandatory parameters"
            return
        }
        Create-Credentials -XDCredentialsProfileName $XDCredentialsProfileName -APIKey $APIKey -CustomerId $CustomerId -SecretKey $SecretKey
        "Credentials created." | Write-Host
        return 0
    }
    "Schedule-Task" {
        if ($User -eq $null -or $Password -eq $null -or $EtcdServer -eq $null -or $EtcdPort -eq $null) {
            Throw "Username and Password are mandatory parameters"
            return
        }
        $mypath = $MyInvocation.MyCommand.Path
        $task = GetorCreate-Task -ScriptPath $mypath `
            -User $User -Password $Password `
            -XDCredentialsProfileName $XDCredentialsProfileName -EtcdServer $EtcdServer -Etcdport $EtcdPort
        return Run-Task -Task $task
    }
    Default {
        "Invalid Action. Only Get-CitrixData or Create-Credentials available" | Write-Host
        return 3
    }
}