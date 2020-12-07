# Most envirnoments will require the script to be signed or the signature verification
# to be disabled. If this requirement is not met, the script can be compiled into an EXE
# using ps2exe-gui from 
# https://gallery.technet.microsoft.com/scriptcenter/PS2EXE-GUI-Convert-e7cb69d5
# then compile the file by using:
# <ps2exe-gui folder>\ps2exe.ps1 -inputfile <path to script>\pre-onboarding.ps1 -outputfilew <output path>\pre-onboarding.exe
#
"Starting to collect user info" | Write-Host
$out = @{}
"Collecting printer info" | Write-Host
$out['printers'] =  get-printer | Where-Object { $_.type -eq "Connection" }
"Collecting network drives info" | Write-Host
$out['drives'] = Get-PSDrive -PSProvider "FileSystem"
"Collecting applications info" | Write-Host
$out['icons'] = @(Get-ChildItem -Recurse "$env:programdata\Microsoft\Windows\Start Menu\Programs\*.lnk" | 
    foreach {
        $_.FullName.SubString("$env:programdata\Microsoft\Windows\Start Menu\Programs\".Length) 
    }
)
$out['icons'] += @(Get-ChildItem -Recurse "$env:appdata\Microsoft\Windows\Start Menu\Programs\*.lnk" | 
    foreach {
        $_.FullName.SubString("$env:appdata\Microsoft\Windows\Start Menu\Programs\".Length) 
    }
)
$out['icons'] += @(Get-ChildItem -Recurse "$env:userprofile\Desktop\*.lnk" | 
    foreach {
        $_.FullName.SubString("$env:userprofile\Desktop\".Length) 
    }
)
$xml = $out | ConvertTo-XML
$bytes = [System.Text.Encoding]::Unicode.GetBytes($xml.OuterXML)
$EncodedText = [Convert]::ToBase64String($bytes)
$sid = ([System.Security.Principal.WindowsIdentity]::GetCurrent()).User.Value
"Uploading data to server" | Write-Host
$res = Invoke-WebRequest -UseBasicParsing -Method "PUT" -Body @{value=$EncodedText  } `
    -Uri "http://workspace.synovus.com/v2/keys/pre-onboarding/$sid" `
    -ContentType "application/x-www-form-urlencoded"
if ($res.StatusCode -eq 201 -or $res.StatusCode -eq 200) {
    Start-Process "http://workspace.synovus.com/pre-onboarding/?sid=$sid"
} else {
    Start-Process "http://workspace.synovus.com/pre-onboarding/failed.html?sid=$sid"
}