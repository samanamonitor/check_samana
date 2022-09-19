$CustomerId='%(CustomerId)s'
$APIKey='%(APIKey)s'
$SecretKey='%(SecretKey)s'
$EtcdServer='%(EtcdServer)s'
$EtcdPort='%(EtcdPort)s'
[string]$BasePath="/samanamonitor/ctx_data"
[int]$MaxRecords=250
[int]$Ttl=360
[int]$DebugLevel=0
[Boolean]$Timing=$True


asnp Citrix.Broker.Admin.V2

Function Epoch {
    return $(Get-Date(Get-Date).ToUniversalTime()-uformat "%%s")
}
Function UrlEncode {
    param([string]$s)
    return [System.web.HttpUtility]::UrlEncode($s)
}

$init_time=Epoch
try {
    Set-XDCredentials -CustomerId $CustomerId -APIKey $APIKey -SecretKey $SecretKey
} catch {
    throw "Credential Profile cannot be found. Aborting."
}
Get-XDAuthentication
return
$sitename=(Get-BrokerSite).Name
$init_time = [Math]::Round((Epoch) - $init_time, 3)

$customerpath="$BasePath/$CustomerId"
$sitepath="$customerpath/$SiteName"

$lastuid=0
$allmachines=@()
$download_time = Epoch
while($true) {
    $m=get-brokermachine -MaxRecordCount $MaxRecords -SortBy Uid -Filter {Uid -gt $lastUid}
    if ($m.Length -eq 0 ) {
        break
    }
    $lastuid = $m[-1].Uid
    $allmachines += $m
}
$download_time = [Math]::Round((Epoch) - $download_time, 3)

$json_time = Epoch
$j = ConvertTo-Json $allmachines
$json_time = [Math]::Round( (Epoch) - $json_time, 3)

$compression_time = Epoch
$Data= foreach ($c in $j.ToCharArray()) {
        $c -as [Byte]
}
$ms = New-Object IO.MemoryStream
$cs = New-Object System.IO.Compression.GZipStream ($ms, [Io.Compression.CompressionMode]"Compress")
$cs.Write($Data, 0, $Data.Length)
$cs.Close()

$a=[Convert]::ToBase64String($ms.ToArray())
"Total data compressed = $($a.Length)" | Write-Host
$ms.Close()
$compression_time = [Math]::Round( (Epoch) - $compression_time, 3)

$upload_time = Epoch
$res = Invoke-WebRequest -Uri "http://$($EtcdServer):$($EtcdPort)/v2/keys$sitepath/raw" `
    -Method Put -Body @{value=$a;ttl=$Ttl} `
    -ContentType "application/x-www-form-urlencoded"
$upload_time = [Math]::Round( (Epoch) - $upload_time, 3)
"Location: $($sitepath)/raw" | Write-Host -NoNewline

" | totaldata=$($j.Length);;;; compressed=$($a.Length);;;; " + `
    "init_time=$init_time;;;; download_time=$download_time;;;; " + `
    "json_time=$json_time;;;; compression_time=$compression_time;;;; " + `
    "upload_time=$upload_time;;;;" | Write-Host