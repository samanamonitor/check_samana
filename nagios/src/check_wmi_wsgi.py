#!/usr/bin/python3

import time
import json
import csv
import sys, getopt
import traceback
from samana.nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
from samana.base import get_dns_ip, ping_host, perf, auth_file
import urllib.request

event_level = 2
event_secs = 300

'''
Using class Win32_PerfRawData_Counters_ProcessorInformation 
  will pull the count of ticks within 100nanosecs
Using class Win32_PerfFormattedData_PerfOS_Processor will 
  probe raw data multiple times and average data. This is why 
  it takes 200ms for the query to respond
'''

ct = time.strptime(time.ctime(time.time() - event_secs))
timefilter = "%04d%02d%02d%02d%02d%02d.000-000" % (ct.tm_year, ct.tm_mon, ct.tm_mday, ct.tm_hour, ct.tm_min, ct.tm_sec)
data = {
    "auth":{
        "username":"",
        "password":"",
        "domain": ""
        },
    "hostname": "",
    "etcdserver": {
        "address": "127.0.0.1",
        "port": "2379",
        "secure": False
        },
    "id-type": "fqdn",
    "warning-str": "",
    "critical-str": "",
    "ttl": 300,
    "queries":[
        {
            "name": "os",
            "namespace": "root\\cimv2",
            "query": "SELECT * FROM Win32_OperatingSystem",
            "class": ""
        },{
            "name": "disk",
            "namespace": "root\\cimv2",
            "query": "SELECT * FROM Win32_LogicalDisk",
            "class": ""
#        },{
#            "name": "cpu",
#            "namespace": "root\\cimv2",
#            "query": "SELECT * FROM Win32_PerfFormattedData_PerfOS_Processor WHERE Name='_Total'" ,
#            "class": ""
        },{
            "name": "pf",
            "namespace": "root\\cimv2",
            "query": "SELECT * FROM Win32_PageFileUsage",
            "class": ""
#        },{
#            "name": "proc",
#            "namespace": "root\\cimv2",
#            "query": "SELECT * FROM Win32_Process",
#            "class": ""
#        },{
#            "name": "services",
#            "namespace": "root\\cimv2",
#            "query" : "SELECT Name, DisplayName, ProcessId, Started, StartName, State, Status FROM Win32_Service",
#            "class": ""
#        },{
#            "name": "evt_system",
#            "namespace": "root\\cimv2",
#            "query": "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'System'" % 
#                (timefilter, 2),
#            "class": ""
#        },{
#            "name": "evt_application",
#            "namespace": "root\\cimv2",
#            "query": "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'Application'" % 
#                (timefilter, 2),
#            "class": ""
#        },{
#            "name": "evt_sf",
#            "namespace": "root\\cimv2",
#            "query": "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'Citrix Delivery Services'" % 
#                (timefilter, 2),
#            "class": ""
        }]
    }


def usage():
  return """Check WMI v2.0.0 WSGI Client
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2021 Samana Group LLC

Usage:
  %s -Y <wmi porxy> -H <host name> ( -U <username> -p <password> | -a <auth file>) [-i <id type>] [-e <etcd server>] [-t <ttl>] [ -w dnswarn,pingwarn,packetlosswarn,wmiwarn ] [ -c dnscrit,pingcrit,packetlosscrit,wmicrit ]

  <wmi proxy>        URL of the WMI proxy server in the form "http://<server>/wmi"
  <host name>        Windows Server to be queried
  <username>         User in Windows Domain (domain\\user) or local Windows user
  <password>         User password
  <auth file>        File containing credentials. In the file, username cannot be UPN.
  <id type>          Id encoding, can be one of "md5", "sha256" or "fqdn". Default is "md5"
  <etcd server>      Etcd server IP/Hostname and port(optional). Default value 127.0.0.1:2379
  <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
""" % sys.argv[0] if len(sys.argv) > 0 else "???????"


def main(argv):
    try:
        opts, args = getopt.getopt(sys.argv[1:], "H:he:t:U:p:w:c:a:i:Y:")
        wmiproxy = None

        for o, a in opts:
            if o == '-H':
                data["hostname"] = a
            elif o == '-Y':
                wmiproxy = a
            elif o == '-U':
                temp = a.split("\\")
                data["auth"]["username"] = temp[0]
                if len(temp) > 1:
                    data["auth"]["domain"] = temp[1]
            elif o == '-p':
                data["auth"]["password"]
            elif o == '-e':
                temp = a.split(':')
                data["etcdserver"]["address"] =temp[0]
                if len(temp) > 1:
                    data["etcdserver"]["port"] = temp[1]
            elif o == '-t':
                ttl = a
            elif o == '-w':
                data["warning-str"] = a
            elif o == '-c':
                data["critical-str"] = a
            elif o == '-a':
                (data["auth"]["username"], data["auth"]["password"], data["auth"]["domain"]) = auth_file(a)
            elif o == "-i":
                data["id-type"] = a
            elif o == '-h':
                raise CheckUnknown("Help", addl=usage())
            else:
                raise CheckUnknown("Unknown Argument '%s'" % a, addl=usage())

        if wmiproxy is None or wmiproxy == "":
            raise CheckUnknown("Invalide WMI proxy URL")
        if data["hostname"] is None or data["hostname"] == "":
            raise CheckUnknown("Host Address not defined")
        if data["auth"]["username"] is None or data["auth"]["username"] == "":
            raise CheckUnknown("Auth data not defined")

        res=urllib.request.urlopen(wmiproxy,data=json.dumps(data).encode('utf-8'))
        outstr=res.read()
        out=json.loads(outstr.decode('utf-8'))

        if out["status"] == 1:
            nagout=CheckWarning(out["info1"], out["perf1"], out["info2"]).result
        elif out["status"] == 2:
            nagout=CheckCritical(out["info1"], out["perf1"], out["info2"]).result
        elif out["status"] == 3:
            nagout=CheckUnknown(out["info1"], out["perf1"], out["info2"]).result
        else:
            nagout=CheckResult(out["info1"], out["perf1"], out["info2"])
    except CheckUnknown as e:
        nagout=e.result

    print(nagout)
    exit(nagout.status)

if __name__ == "__main__":
  main(sys.argv)
