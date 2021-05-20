param(
    $SamanaMonitorURI = "",
    $MemCachedServer = "",
    $MemCachedPort = "11211",
    $idMethod = "md5",
    $EtcdServer = "",
    $EtcdPort = "2379",
    $EtcdProtocol = "http",
    $ttl = 900
)

if ( $SamanaMonitorURI -eq "" -and $EtcdServer -ne "") {
    $SamanaMonitorURI = "{0}://{1}:{2}" -f $EtcdProtocol,$EtcdServer,$EtcdPort
}

if ( $SamanaMonitorURI -eq "") {
    "Need an ETCD server defined" | Out-Host
    return
}

$config = @{
EventMinutes = 10
EventMax = 10
EventLevelMax = 3
EventList = @("System", "Application")
}
# End Default parameters

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

Function Send-Data {
    param( 
    $ServerIp, 
    $ServerPort, 
    $ttl,
    $key,
    $data )
    $tcpConnection = New-Object System.Net.Sockets.TcpClient($ServerIp, $ServerPort)
    $tcpStream = $tcpConnection.GetStream()
    $reader = New-Object System.IO.StreamReader($tcpStream)
    $writer = New-Object System.IO.StreamWriter($tcpStream)
    $writer.AutoFlush = $true
    while ($tcpConnection.Connected) {
        while ($tcpStream.DataAvailable)
        {
            $res = $reader.ReadLine()
        }
        if($res -eq "STORED" -or $res -eq "ERROR") {
            $writer.WriteLine("quit")
            break
        }
        $set = "set {0} 0 {1} {2}" -f $key, $ttl, $data.length
        $writer.WriteLine($set)
        $writer.WriteLine($data)
        while (!$tcpStream.DataAvailable) {}
    }
    $reader.Close()
    $writer.Close()
    $tcpConnection.Close()
    return $res
}

$data = @{}

$data['epoch'] =[Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
$query = "select DNSHostName, Domain from win32_computersystem"
$computer = Get-WmiObject -Query $query
$data['DNSHostName'] = $computer.DNSHostName
$data['Domain'] = $computer.Domain

$ComputerFQDN = "$($data['DNSHostName']).$($data['Domain'])"
$utf8 = New-Object -TypeName System.Text.UTF8Encoding
if($idMethod -eq "md5") {
    $hash = New-Object -TypeName System.Security.Cryptography.MD5CryptoServiceProvider
    $ComputerID = [System.BitConverter]::ToString($hash.ComputeHash($utf8.GetBytes($ComputerFQDN))) -Replace '-'
} elseif ($idMethod -eq "sha256") {
    $hash = New-Object -TypeName System.Security.Cryptography.SHA256CryptoServiceProvider
    $ComputerID = [System.BitConverter]::ToString($hash.ComputeHash($utf8.GetBytes($ComputerFQDN))) -Replace '-'
} elseif ($idMethod -eq "fqdn") {
    $ComputerID = $ComputerFQDN.ToLower()
} else {
    "Invalid id method. Use one: md5, sha256 or fqdn" | Out-Host
    return
}

get-config -ServerUri $SamanaMonitorURI -Location "samanamonitor/config/global" -Config $config
get-config -ServerUri $SamanaMonitorURI -Location "samanamonitor/config/$($ComputerID)" -Config $config

$data['ID'] = $ComputerID
$query = "select PercentIdleTime, PercentInterruptTime, " + `
    "PercentPrivilegedTime, PercentProcessorTime, PercentUserTime from " + `
    "Win32_PerfFormattedData_PerfOS_Processor where name=""_Total"""
$Processor=Get-WmiObject -Query $query

$data['PercentIdleTime'] = $Processor.PercentIdleTime
$data['PercentInterruptTime'] = $Processor.PercentInterruptTime
$data['PercentPrivilegedTime'] = $Processor.PercentPrivilegedTime
$data['PercentProcessorTime'] = $Processor.PercentProcessorTime
$data['PercentUserTime'] = $Processor.PercentUserTime

$query = "select FreePhysicalMemory, FreeSpaceInPagingFiles, " + `
    "FreeVirtualMemory, SizeStoredInPagingFiles, TotalVirtualMemorySize, " + `
    "TotalVisibleMemorySize, NumberOfProcesses, LastBootUpTime, " + `
    "CSName from win32_operatingsystem"
$Server=Get-WmiObject -Query $query
$data['FreePhysicalMemory'] = $Server.FreePhysicalMemory
$data['FreeSpaceInPagingFiles'] = $Server.FreeSpaceInPagingFiles
$data['FreeVirtualMemory'] = $Server.FreeVirtualMemory
$data['TotalSwapSpaceSize'] = $Server.SizeStoredInPagingFiles
$data['TotalVirtualMemorySize'] = $Server.TotalVirtualMemorySize
$data['TotalVisibleMemorySize'] = $Server.TotalVisibleMemorySize
$data['NumberOfProcesses'] = $Server.NumberOfProcesses
$data['UpTime'] = ([datetime](get-date).datetime - $Server.ConverttoDateTime($server.LastBootUpTime)).totalhours
$data['Services'] = Get-Service


$query = "Select * from win32_logicaldisk"
$data['Disks'] = Get-WmiObject -Query $query

$data['Events'] = @{}
foreach($e in $config['EventList']) {
    $query = @"
<QueryList>
  <Query Id="0">
    <Select Path="$($e)">
        *[System[(Level &lt;= $($config['EventLevelMax'])) and
        TimeCreated[timediff(@SystemTime) &lt;= $($config['EventMinutes'] * 60000)]]]
    </Select>
  </Query>
</QueryList>
"@
    try {
        $evts = Get-WinEvent -FilterXML $query -EA silentlycontinue
        $data['Events'][$e] = @()
        if ($evts.Count -gt $config['EventMax']) {
            $data['Events']['Truncated'] += @($e)
            $data['Events'][$e] = $evts[0..($config['EventMax']-1)]
        } else {
            $data['Events'][$e] += @($evts)
        }
    } catch {
        $data['Events'][$e] = "Invalid Event Log"
    }
}

$value = $data | ConvertTo-JSON -Compress
if ( $MemCachedServer -ne "") {
    $res = Send-Data $MemCachedServer 11211 300 $ComputerID $value
}
$res
if ($SamanaMonitorURI -ne "") {
    $res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$value; ttl=$ttl} `
        -uri "$($SamanaMonitorURI)/v2/keys/samanamonitor/data/$($ComputerID)" `
        -ContentType "application/x-www-form-urlencoded"
}
$ComputerID | Out-Host
