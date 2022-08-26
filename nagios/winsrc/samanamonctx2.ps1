param(
    $SamanaMonitorURI = "",
    $MemCachedServer = "",
    $MemCachedPort = "11211",
    $idMethod = "md5",
    $EtcdServer = "",
    $EtcdPort = "2379",
    $EtcdProtocol = "http",
    $ttl = 300
)

if ( $SamanaMonitorURI -eq "" -and $EtcdServer -ne "") {
    $SamanaMonitorURI = "{0}://{1}:{2}" -f $EtcdProtocol,$EtcdServer,$EtcdPort
}

if ( $SamanaMonitorURI -eq "") {
    "Need an ETCD server defined" | Out-Host
    return
}

$config = @{}

Function get-config {
    param( $ServerUri, $Location, $Config )
    $uri = "$($ServerUri)/v2/keys/$($Location)"
    try {
        $temp_config = ((Invoke-WebRequest -UseBasicParsing -Uri $uri).Content `
            | ConvertFrom-Json).node.value | ConvertFrom-Json
        $temp_config.PSObject.Properties | ForEach-Object {
            $Config[$_.Name] = $_.Value
        }

    } catch {}
}

Function create-definition {
    param( $m )
    $def=@{}
    $m | Get-Member | ForEach {
        $member=$_.Name
        if ($m."$member" -ne $null ) {
            $t=($m."$member").GetType()
            if($t.BaseType.ToString() -eq "System.Enum") {
                $def[$member] = @{}
                [Enum]::GetNames($t.FullName)  | % {
                    $num = $t::$_.value__
                    $def[$member]["$num"]=$_
                }
            }
        }
    }
    return $def
}

class EtcdConnection {
    [string]$URI
    EtcdConnection([string]$URI) {
        $this.URI = $URI
    }
    [PSObject]Get([string]$Key) {
        try {
            $res = Invoke-WebRequest -UseBasicParsing -Method "GET" `
                -uri "$($this.URI)/v2/keys/$Key"
            $out = ConvertFrom-Json $res.Content         
        } catch {
            $out = ConvertFrom-Json $_.ErrorDetails
        }
        return $out

    }
    [PSObject]Rm([string]$Key) {
        try {
            $res = Invoke-WebRequest -UseBasicParsing -Method "DELETE" `
                -uri "$($this.URI)/v2/keys/$Key"
            $out = ConvertFrom-Json $res.Content
        } catch {
            $out = ConvertFrom-Json $_.ErrorDetails
        }
        return $out

    }
    [PSObject]Set([string]$Key, [string]$Value) {
        try {
            $res = Invoke-WebRequest -UseBasicParsing -Method "PUT" `
                -Body @{value=$Value} `
                -uri "$($this.URI)/v2/keys/$Key" `
                -ContentType "application/x-www-form-urlencoded"
            $out = ConvertFrom-Json $res.Content
        } catch {
            $out = ConvertFrom-Json $_.ErrorDetails
        }
        return $out

    }
    [PSObject]Set([string]$Key, [string]$Value, [int]$TTL) {
        try {
            $res = Invoke-WebRequest -UseBasicParsing -Method "PUT" `
                -Body @{value=$Value; ttl=$TTL} `
                -uri "$($this.URI)/v2/keys/$Key" `
                -ContentType "application/x-www-form-urlencoded"
            $out = ConvertFrom-Json $res.Content
        } catch {
            $out = ConvertFrom-Json $_.ErrorDetails
        }
        return $out
    }
}

class SamanaMon {
    [PSObject]$e
    [hashtable]$config
    CtxSamanaMon([string]$URI) {
        $this.e = [EtcdConnection]::new($URI)
        $this.config = @{}
    }
    GetConfig() {
        try {
            $t = $this.e.Get("samanamonitor/config/global")
            if ($t.errorCode -ne $null) {
                return
            }
            $t1 = $t.node.value | ConvertFrom-Json
            $t1.PSObject.Properties | ForEach-Object {
                $this.config[$_.Name] = $_.Value
            }
        } catch {
            return
        }
    }
    GetConfig([string]$Hostname) {
        $this.GetConfig()
        try {
            $t = $this.e.Get("samanamonitor/config/$Hostname")
            if ($t.errorCode -ne $null) {
                return
            }
            $t1 = $t.node.value | ConvertFrom-Json
            $t1.PSObject.Properties | ForEach-Object {
                $this.config[$_.Name] = $_.Value
            }
        } catch {
            return
        }
    }
}

Add-PSSnapin Citrix.*

$ComputerName=$env:COMPUTERNAME.ToLower()
$Farm = @{
    "TotalServers"=0; 
    "LoadIndex"=0; 
    "SessionCount"=0; 
    "InMaintenanceMode" = 0; 
    "Registered" = 0;
}
$DesktopGroup = @{}
Get-BrokerDesktopGroup -MaxRecordCount 5000 | ForEach {
    $DesktopGroup[$_.Name.ToLower()] = @{
        "TotalServers"=0; 
        "LoadIndex"=0; 
        "SessionCount"=0; 
        "InMaintenanceMode" = 0; 
        "Registered" = 0;
    }
}
$DesktopGroup["none"] = @{
    "TotalServers"=0; 
    "LoadIndex"=0; 
    "SessionCount"=0; 
    "InMaintenanceMode" = 0; 
    "Registered" = 0;
}

$definitions = $null
$e = [EtcdConnection]::new($SamanaMonitorURI)

Get-BrokerMachine -MaxRecordCount 5000 | ForEach {
    if ($definitions -eq $null) {
        $definitions = create-definition $_
    }
    if($_.DesktopGroupName -eq $null) {
        $dg = $DesktopGroup["none"]
    } else {
        $dg = $DesktopGroup[$_.DesktopGroupName.ToLower()]
    }
    $dg["TotalServers"] += 1
    $Farm["TotalServers"] += 1
    $dg["SessionCount"] += $_.SessionCount
    $Farm["SessionCount"] += $_.SessionCount
    if ($_.RegistrationState -eq "Registered" -and -not $_.InMaintenanceMode) {
        $dg["LoadIndex"] += $_.LoadIndex
        $Farm["LoadIndex"] += $_.LoadIndex
    } else {
        $dg["LoadIndex"] += 10000
        $Farm["LoadIndex"] += 10000
    }
    if ($_.RegistrationState -eq "Registered") {
        $dg["Registered"] += 1
        $Farm["Registered"] += 1
    }
    if ($_.InMaintenanceMode) {
        $dg["InMaintenanceMode"] += 1
        $Farm["InMaintenanceMode"] += 1
    }

    $epoch = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
    $_ | Add-Member -NotePropertyName epoch -NotePropertyValue 0
    $_.epoch = $epoch
    $_ | Add-Member -NotePropertyName Definitions -NotePropertyValue $definitions
    $value = $_ | ConvertTo-JSON -Compress
    if ($_.DnsName -ne "" ) {
        $e.Set("samanamonitor/ctx_data/$($ComputerName)/hosts/$($_.DnsName.ToLower())", $value, $ttl)
    }
}

$DesktopGroup.Keys | ForEach {
    $dg = $DesktopGroup[$_.ToLower()]
    if ($dg['TotalServers'] -gt 0) {
       $dg['LoadIndex'] /= $dg['TotalServers']
    } else {
        $dg['LoadIndex'] = 10000
    }
    $dg["epoch"] = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
    $value = $dg | ConvertTo-JSON -Compress
    $res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$value; ttl=$ttl} `
        -uri "$($SamanaMonitorURI)/v2/keys/samanamonitor/ctx_data/$($ComputerName)/desktopgroup/$($_)" `
        -ContentType "application/x-www-form-urlencoded"

}
$Farm["epoch"] = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
$Farm['LoadIndex'] /= $Farm['TotalServers']
$value = $Farm | ConvertTo-JSON -Compress
$res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$value; ttl=$ttl} `
    -uri "$($SamanaMonitorURI)/v2/keys/samanamonitor/ctx_data/$($ComputerName)/farm" `
    -ContentType "application/x-www-form-urlencoded"

$ComputerName | Out-Host
