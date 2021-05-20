#!/usr/bin/python3

import pywmi
import time
import json
import samanaetcd as etcd
import csv
import sys, getopt
import traceback

timeout=60
event_level = 2
event_secs = 300

queries = {
    'os': "SELECT * FROM Win32_OperatingSystem",
    'disk': "SELECT * FROM Win32_LogicalDisk",
    'cpu': "SELECT * FROM Win32_PerfRawData_PerfOS_Processor WHERE Name='_Total'" ,
    'pf': "SELECT * FROM Win32_PageFileUsage",
    'evt_system':
        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'System'",
    'evt_application':
        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'Application'",
    'evt_sf':
        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'Citrix Delivery Services'",
    'proc': 'SELECT * FROM Win32_Process',
    'computer': "SELECT * FROM Win32_ComputerSystem"
}


class CheckNagiosException(Exception):
    def __init__(self, info=None, perf_data=None, addl=None):
        self.info = info if info is not None else "Unknown Exception"
        self.perf_data = " | %s" % perf_data if perf_data is not None else ""
        self.addl = "\n%s" % addl if addl is not None else ""

class CheckNagiosWarning(CheckNagiosException):
    pass

class CheckNagiosError(CheckNagiosException):
    pass

class CheckNagiosUnknown(CheckNagiosException):
    pass


def usage(argv):
  return """Check WMI v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2021 Samana Group LLC

Usage:
  %s -H <host name> -U <username> -p <password> [-n <namespace>] [-e <etcd server>] [-t <ttl>]

  <host name>        Windows Server to be queried
  <username>         User in Windows Domain (domain\\user or user@domain) or local Windows user
  <password>         User password
  <namespace>        WMI namespace, default root\\cimv2
  <etcd server>      Etcd server IP/Hostname and port(optional). Default value 127.0.0.1:2379
  <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
""" % argv[0] if len(argv) > 0 else "???????"


def query_server(host, username, password, namespace="root\\cimv2", filter_tuples={}):
    ''' param:filter_tuples is a dictionary where keys matches the key in queries global dictionary
        if the key doesn't exist, then an empty tuple is expected, otherwise the tuple
        must contain all the arguments needed to complete the string
    '''
    server = {}
    pywmi.open(host, username, password, namespace)
    for i in queries.keys():
        server[i] = pywmi.query(queries[i] % filter_tuples.get(i, ()))
    pywmi.close()
    return server

def wmiresponse(input_text):
    pass


def main(argv):
    try:
        etcdserver = '127.0.0.1'
        etcdport = '2379'
        opts, args = getopt.getopt(sys.argv[1:], "H:he:t:U:p:n:")
        ttl = 300
        hostaddress = None
        username = None
        password = None
        namespace = "root\\cimv2"

        for o, a in opts:
            if o == '-H':
                hostaddress = a
            elif o == '-U':
                username = a
            elif o == '-p':
                password = a
            elif o == 'n':
                namespace = a
            elif o == '-e':
                temp = a.split(':')
                etcdserver =temp[0]
                if len(temp) > 1:
                    etcdport = temp[1]
            elif o == '-t':
                ttl = a
            elif o == '-h':
                raise CheckNagiosUnknown("Help", addl=usage())
            else:
                raise CheckNagiosUnknown("Unknown Argument", addl=usage())

        if hostaddress is None:
            raise CheckNagiosUnknown("Host Address not defined")
        if username is None:
            raise CheckNagiosUnknown("Auth file not defined")

        ct = time.strptime(time.ctime(time.time() - event_secs))
        timefilter = "%04d%02d%02d%02d%02d%02d.000-000" % (ct.tm_year, ct.tm_mon, ct.tm_mday, ct.tm_hour, ct.tm_min, ct.tm_sec)

        #select * from Win32_NTLogEvent where TimeGenerated > '20210505120200.000-240'
        filter_tuples = {
            'evt_application': (timefilter, 2),
            'evt_system': (timefilter, 2),
            'evt_sf': (timefilter, 2)
        }
        a = query_server(hostaddress, username, password, namespace=namespace, filter_tuples=filter_tuples)
        computer = a['computer'][0]['properties']
        cpu = a['cpu'][0]['properties']
        data = {
            'epoch': int(time.time()),
            'DNSHostName': computer['DNSHostName'],
            'Domain': computer['Domain'],
            'ID': "%s.%s" %  (computer['DNSHostName'], computer['Domain']),
            'PercentIdleTime': int(cpu['PercentIdleTime'] / cpu['Timestamp_PerfTime'] * 100),
            'PercentInterruptTime': int(cpu['PercentInterruptTime'] / cpu['Timestamp_PerfTime'] * 100),
            'PercentPrivilegedTime': int(cpu['PercentPrivilegedTime'] / cpu['Timestamp_PerfTime'] * 100),
            'PercentProcessorTime': int(cpu['PercentProcessorTime'] / cpu['Timestamp_PerfTime'] * 100),
            'PercentUserTime': int(cpu['PercentUserTime'] / cpu['Timestamp_PerfTime'] * 100),

        }

        print("OK - %s | %s\n%s" % (json.dumps(a), json.dumps(data), ""))
    except CheckNagiosWarning as e:
        print("WARNING - %s%s%s" % (e.info, e.perf_data, e.addl))
        exit(1)
    except CheckNagiosError as e:
        print("ERROR - %s%s%s" % (e.info, e.perf_data, e.addl))
        exit(2)
    except CheckNagiosUnknown as e:
        print("UNKNOWN - %s%s%s" % (e.info, e.perf_data, e.addl))
        exit(3)
    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        print("UNKNOWN - Error: %s at line %s\n%s" % (str(e), tb.tb_lineno, traceback_info.format()))
        exit(3)

if __name__ == "__main__":
  main(sys.argv)
