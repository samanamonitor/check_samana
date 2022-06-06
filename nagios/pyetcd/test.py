#!/usr/bin/python3

from samana.etcd import Client
a = Client(host="172.17.0.2", port=2379)
print(a)
a
data='''[{"classname": "Win32_OperatingSystem", "properties": {"BootDevice": "\\\\Device\\\\HarddiskVolume1", "BuildNumber": "14393", "BuildType": "Multiprocessor Free", "Caption": "Microsoft Windows Server 2016 Datacenter", "CodeSet": "1252", "CountryCode": "1", "CreationClassName": "Win32_OperatingSystem", "CSCreationClassName": "Win32_ComputerSystem", "CSDVersion": null, "CSName": "SMNNOVMSDC1", "CurrentTimeZone": -240, "DataExecutionPrevention_32BitApplications": true, "DataExecutionPrevention_Available": true, "DataExecutionPrevention_Drivers": true, "DataExecutionPrevention_SupportPolicy": 3, "Debug": false, "Description": "", "Distributed": false, "EncryptionLevel": 256, "ForegroundApplicationBoost": 2, "FreePhysicalMemory": 3106200, "FreeSpaceInPagingFiles": 583768, "FreeVirtualMemory": 3790040, "InstallDate": "20190307185432.000000-300", "LargeSystemCache": 0, "LastBootUpTime": "20220528190011.499993-240", "LocalDateTime": "20220531094515.892000-240", "Locale": "0409", "Manufacturer": "Microsoft Corporation", "MaxNumberOfProcesses": 4294967295, "MaxProcessMemorySize": 137438953344, "MUILanguages": ["en-US"], "Name": "Microsoft Windows Server 2016 Datacenter|C:\\\\Windows|\\\\Device\\\\Harddisk0\\\\Partition2", "NumberOfLicensedUsers": 0, "NumberOfProcesses": 43, "NumberOfUsers": 4, "OperatingSystemSKU": 8, "Organization": "", "OSArchitecture": "64-bit", "OSLanguage": 1033, "OSProductSuite": 400, "OSType": 18, "OtherTypeDescription": null, "PAEEnabled": false, "PlusProductID": null, "PlusVersionNumber": null, "PortableOperatingSystem": false, "Primary": true, "ProductType": 2, "RegisteredUser": "Windows User", "SerialNumber": "00376-50001-24186-AA563", "ServicePackMajorVersion": 0, "ServicePackMinorVersion": 0, "SizeStoredInPagingFiles": 720896, "Status": "OK", "SuiteMask": 400, "SystemDevice": "\\\\Device\\\\HarddiskVolume2", "SystemDirectory": "C:\\\\Windows\\\\system32", "SystemDrive": "C:", "TotalSwapSpaceSize": 0, "TotalVirtualMemorySize": 4914660, "TotalVisibleMemorySize": 4193764, "Version": "10.0.14393", "WindowsDirectory": "C:\\\\Windows"}}]'''

a.put("/samanamonitor2/key123", "value123")
#print(a.set("/samanamonitor2/key122", value="value123"))
#print(a.set(key="/samanamonitor2/key123", value="value123"))
#
#print(a.set(key="/samanamonitor2/key123", value=data, ttl=600))
#
#import json
#res=a.get("/samanamonitor2/key123")
#
#def test():
#    a.get()