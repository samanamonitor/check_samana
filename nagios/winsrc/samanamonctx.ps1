#$SamanaMonitorURI = "http://%NAGIOS_IP%:2379"
param($SamanaMonitorURI)

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

Add-PSSnapin Citrix.*

$ComputerName=$env:COMPUTERNAME.ToLower()
$Farm = @{
    "TotalServers"=0; 
    "TotalLoad"=0; 
    "SessionCount"=0; 
    "InMaintenanceMode" = 0; 
    "Registered" = 0;
}
$DesktopGroup = @{}
Get-BrokerDesktopGroup -MaxRecordCount 5000 | ForEach {
    $DesktopGroup[$_.Name.ToLower()] = @{
        "TotalServers"=0; 
        "TotalLoad"=0; 
        "SessionCount"=0; 
        "InMaintenanceMode" = 0; 
        "Registered" = 0;
    }
}

Get-BrokerMachine -MaxRecordCount 5000 | ForEach {
    $dg = $DesktopGroup[$_.DesktopGroupName.ToLower()]
    $dg["TotalServers"] += 1
    $Farm["TotalServers"] += 1
    $dg["SessionCount"] += $_.SessionCount
    $Farm["SessionCount"] += $_.SessionCount
    if ($_.RegistrationState -eq "Registered" -and -not $_.InMaintenanceMode) {
        $dg["TotalLoad"] += $_.LoadIndex
        $Farm["TotalLoad"] += $_.LoadIndex
    } else {
        $dg["TotalLoad"] += 10000
        $Farm["TotalLoad"] += 10000
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
    $value = $_ | ConvertTo-JSON -Compress
    $res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$value} `
        -uri "$($SamanaMonitorURI)/v2/keys/samanamonitor/ctx_data/$($ComputerName)/hosts/$($_.DnsName.ToLower())" `
        -ContentType "application/x-www-form-urlencoded"
}

$DesktopGroup.Keys | ForEach {
    $dg = $DesktopGroup[$_.ToLower()]
    $dg["epoch"] = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
    $value = $dg | ConvertTo-JSON -Compress
    $res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$value} `
        -uri "$($SamanaMonitorURI)/v2/keys/samanamonitor/ctx_data/$($ComputerName)/desktopgroup/$($_)" `
        -ContentType "application/x-www-form-urlencoded"

}
$Farm["epoch"] = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
$value = $Farm | ConvertTo-JSON -Compress
$res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$value} `
    -uri "$($SamanaMonitorURI)/v2/keys/samanamonitor/ctx_data/$($ComputerName)/farm" `
    -ContentType "application/x-www-form-urlencoded"

$ComputerName | Out-Host