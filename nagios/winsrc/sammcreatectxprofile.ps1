asnp Citrix.Broker.Admin.V2
Switch($Action) {
    "Create-Profile" {
        if ($CustomerId -eq $null -or $APIKey -eq $null -or $SecretKey -eq $null -or $ProfileName -eq $null) {
            throw "Invalid Set of parameters. CustomerId, APIKey, SecretKey and ProfileName are mandatory"            
        }
        Set-XDCredentials -CustomerId $CustomerId -APIKey $APIKey -SecretKey $SecretKey -StoreAs $ProfileName
    }
    "List-Profiles" {
        Get-XDCredentials -ListProfiles
    }
    "Delete-Profile" {
        if ($ProfileName -eq $null) {
            throw "Invalid Set of parameters. ProfileName is mandatory"            
        }
        Clear-XDCredentials -ProfileName $ProfileName
    }
    "Show-Profile" {
        if ($ProfileName -eq $null) {
            throw "Invalid Set of parameters. ProfileName is mandatory"            
        }
        $p = Get-XDCredentials -ProfileName $ProfileName
        $p.Credentials
    }
    Default {
        throw "Invalid Action"
    }
}
