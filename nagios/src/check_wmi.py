#!/usr/bin/python3

import pywmi
import time
import json
import samanaetcd as etcd
import csv
import sys, getopt
import traceback
import re

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
    'services': 'SELECT * FROM Win32_Service',
    'computer': "SELECT * FROM Win32_ComputerSystem"
}


class CheckNagiosException(Exception):
    def __init__(self, info=None, perf_data=None, addl=None):
        self.info = info if info is not None else "Unknown Exception"
        self.perf_data = " | %s" % perf_data if perf_data is not None else ""
        self.addl = "\n%s" % addl if addl is not None else ""

class CheckNagiosWarning(CheckNagiosException):
    pass

class CheckNagiosCritical(CheckNagiosException):
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
  %s -H <host name> -U <username> -p <password> [-n <namespace>] [-e <etcd server>] [-t <ttl>] [ -w dnswarn,pingwarn,packetlosswarn,wmiwarn ] [ -c dnscrit,pingcrit,packetlosscrit,wmicrit ]

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
    conn_status = pywmi.open(host, username, password, namespace)
    if conn_status != 0:
        raise CheckNagiosUnknown("Unable to connecto to server. Error %s" % conn_status)
    for i in queries.keys():
        server[i] = pywmi.query(queries[i] % filter_tuples.get(i, ()))
        if not isinstance(server[i], list):
            raise CheckNagiosUnknown("Error connecting to server %08x" % server[i])
    pywmi.close()
    return server

def legacy(indata):
    computer = indata['computer'][0]['properties']
    cpu = indata['cpu'][0]['properties']
    os = indata['os'][0]['properties']
    TotalSwapSpaceSize = 0
    for i in indata['pf']:
        TotalSwapSpaceSize += i['properties']['AllocatedBaseSize']

    t = os['LastBootUpTime'].split('.')[0]
    z = int(os['LastBootUpTime'][-4:])
    zh = abs(int(z / 60))
    zm = int(z % 60)
    sign = '-' if z < 0 else '+'
    st = time.strptime("%s%s%02d%02d" % (t, sign, zh, zm), "%Y%m%d%H%M%S%z")
    return {
        'epoch': int(time.time()),
        'DNSHostName': computer['DNSHostName'],
        'Domain': computer['Domain'],
        'ID': "%s.%s" %  (computer['DNSHostName'], computer['Domain']),
        'PercentIdleTime': int(cpu['PercentIdleTime'] / cpu['Timestamp_PerfTime'] * 100),
        'PercentInterruptTime': int(cpu['PercentInterruptTime'] / cpu['Timestamp_PerfTime'] * 100),
        'PercentPrivilegedTime': int(cpu['PercentPrivilegedTime'] / cpu['Timestamp_PerfTime'] * 100),
        'PercentProcessorTime': int(cpu['PercentProcessorTime'] / cpu['Timestamp_PerfTime'] * 100),
        'PercentUserTime': int(cpu['PercentUserTime'] / cpu['Timestamp_PerfTime'] * 100),
        'FreePhysicalMemory': os['FreePhysicalMemory'],
        'FreeSpaceInPagingFiles': os['FreeSpaceInPagingFiles'],
        'FreeVirtualMemory': os['FreeVirtualMemory'],
        'TotalSwapSpaceSize': TotalSwapSpaceSize,
        'TotalVirtualMemorySize': os['TotalVirtualMemorySize'],
        'TotalVisibleMemorySize': os['TotalVisibleMemorySize'],
        'NumberOfProcesses': os['NumberOfProcesses'],
        'UpTime': time.time() - (time.mktime(st) + st.tm_gmtoff) / 3600,
        'Services': indata['services'],
        'Events': {
            'System': indata['evt_system'],
            'Application': indata['evt_application'],
            'Citrix Delivery Services': indata['evt_sf']
        }
    }


def ping_host(ip):
    import subprocess
    data={
        'packets_sent': 0,
        'packets_received': 0,
        'min': 0,
        'avg': 0,
        'max': 0,
        'mdev': 0
    }
    p = subprocess.Popen(["ping", "-c", "3", ip], stdout = subprocess.PIPE)
    out = p.communicate()
    packets = None
    rtt = None
    try:
        outstr = out[0].decode('utf8')
        pat = re.search("^(\d+) packets transmitted, (\d+) packets received", outstr, flags=re.M)
        if pat is None:
            raise ValueError("Cannot extract packets from ping output.")
        packets = pat.groups()

        pat = re.search("^round-trip min/avg/max/stddev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", outstr, flags=re.M)
        if pat is None:
            raise ValueError("Cannot extract ping rtt times.")
        rtt = pat.groups()

        data['packets_sent'] = int(packets[0])
        data['packets_received'] = int(packets[1])
        data['min'] = int(float(rtt[0]))
        data['avg'] = int(float(rtt[1]))
        data['max'] = int(float(rtt[2]))
        data['mdev'] = int(float(rtt[3]))
    except (ValueError, IndexError) as e:
        raise CheckNagiosUnknown("Ping output invalid. %s\n%s" % (str(e), outstr))
    except Exception as e:
        raise CheckNagiosUnknown("unexpected error %s\n%s\n%s\n%s" % (str(e), outstr, packets, rtt))
    return data

def get_dns_ip(hn):
    import socket

    pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if pat.match(hn):
        return (hn, 0)

    try:
        dns_start = time.time()
        server_data = socket.gethostbyname_ex(hn)
        ips = server_data[2]
        if not isinstance(ips, list) and len(ips) != 1:
            raise ValueError("hostname is linked to more than 1 IP or 0 IPs")
        dns_time = (time.time() - dns_start) * 1000

    except ValueError as err:
        raise CheckNagiosUnknown("%s" % str(err))
    except IndexError as err:
        raise CheckNagiosUnknown("Invalid data received from gethostbyname_ex %s" % str(err), addl=server_data)
    except Exception as err:
        raise CheckNagiosCritical("Unable to resove hostname to IP address", addl=str(err))

    return (ips[0], dns_time)

def main(argv):
    try:
        etcdserver = '127.0.0.1'
        etcdport = '2379'
        opts, args = getopt.getopt(sys.argv[1:], "H:he:t:U:p:n:w:c:")
        ttl = 300
        hostaddress = None
        username = None
        password = None
        namespace = "root\\cimv2"
        url = None
        warning = None
        critical = None
        ping_warn = None
        ping_crit = None
        wmi_warn = None
        wmi_crit = None
        dns_warn = None
        dns_crit = None
        packet_loss_warn = None
        packet_loss_crit = None

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
            elif o == '-w':
                warning = a
            elif o == '-c':
                critical = a
            elif o == '-h':
                raise CheckNagiosUnknown("Help", addl=usage())
            else:
                raise CheckNagiosUnknown("Unknown Argument", addl=usage())

        if hostaddress is None:
            raise CheckNagiosUnknown("Host Address not defined")
        if username is None:
            raise CheckNagiosUnknown("Auth data not defined")

        if warning is not None:
            try:
                (dns_warn, ping_warn, packet_loss_warn, wmi_warn) = warning.split(',')
                dns_warn = int(dns_warn)
                ping_warn = int(ping_warn)
                packet_loss_warn = int(packet_loss_warn)
                wmi_warn = int(wmi_warn)
            except ValueError:
                raise CheckNagiosUnknown("Invalid Warning values")

        if critical is not None:
            try:
                (dns_crit, ping_crit, packet_loss_crit, wmi_crit) = critical.split(',')
                dns_crit = int(dns_crit)
                ping_crit = int(ping_crit)
                packet_loss_crit = int(packet_loss_crit)
                wmi_crit = int(wmi_crit)
            except ValueError:
                raise CheckNagiosUnknown("Invalid Critical values")

        ct = time.strptime(time.ctime(time.time() - event_secs))
        timefilter = "%04d%02d%02d%02d%02d%02d.000-000" % (ct.tm_year, ct.tm_mon, ct.tm_mday, ct.tm_hour, ct.tm_min, ct.tm_sec)

        filter_tuples = {
            'evt_application': (timefilter, 2),
            'evt_system': (timefilter, 2),
            'evt_sf': (timefilter, 2)
        }

        (hostip, dns_time) = get_dns_ip(hostaddress)
        ping_data = ping_host(hostip)

        wmi_start = time.time()
        a = query_server(hostaddress, username, password, namespace=namespace, filter_tuples=filter_tuples)
        wmi_time = (time.time() - wmi_start) * 1000

        data = legacy(a)

        perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])

        perf_data = "dns_resolution=%d;%s;%s;; ping_perc_packet_loss=%d;%s;%s;; ping_rtt=%d;%s;%s;; wmi_time=%d;%s;%s;;" % \
            (dns_time, dns_warn if dns_warn is not None else '', dns_crit if dns_crit is not None else '',
                perc_packet_loss, packet_loss_warn if packet_loss_warn is not None else '', packet_loss_crit if packet_loss_crit is not None else '',
                ping_data['avg'], ping_warn if ping_warn is not None else '', ping_crit if ping_crit is not None else '', 
                wmi_time, wmi_warn if wmi_warn is not None else '', wmi_crit if wmi_crit is not None else '')

        c = etcd.Client(host=etcdserver, port=etcdport)
        c.put("/samanamonitor/data/%s" % data['ID'].lower(), json.dumps(data), ttl)

        if dns_crit is not None and dns_crit < dns_time:
            raise CheckNagiosCritical("DNS name resolution took longer than expected %d" % dns_time, perf_data=perf_data, addl=out)
        if dns_warn is not None and dns_warn < dns_time:
            raise CheckNagiosWarning("DNS name resolution took longer than expected %d" % dns_time, perf_data=perf_data, addl=out)
        if packet_loss_crit is not None and packet_loss_crit < perc_packet_loss:
            raise CheckNagiosCritical("PING lost %d%% packets" % perc_packet_loss, perf_data=perf_data, addl=out)
        if packet_loss_warn is not None and packet_loss_warn < perc_packet_loss:
            raise CheckNagiosWarning("PING lost %d%% packets" % perc_packet_loss, perf_data=perf_data, addl=out)
        if ping_crit is not None and ping_crit < ping_data['avg']:
            raise CheckNagiosCritical("PING rtt is greater than expected %d ms" % ping_data['avg'], perf_data=perf_data, addl=out)
        if ping_warn is not None and ping_warn < ping_data['avg']:
            raise CheckNagiosWarning("PING rtt is greater than expected %d ms" % ping_data['avg'], perf_data=perf_data, addl=out)
        if winrm_crit is not None and winrm_crit < winrm_time:
            raise CheckNagiosCritical("WMI took longer than expected %d ms" % wmi_time, perf_data=perf_data, addl=out)
        if winrm_warn is not None and winrm_warn < winrm_time:
            raise CheckNagiosWarning("WMI took longer than expected %d ms" % wmi_time, perf_data=perf_data, addl=out)

    except CheckNagiosWarning as e:
        print("WARNING - %s%s%s" % (e.info, e.perf_data, e.addl))
        exit(1)
    except CheckNagiosCritical as e:
        print("CRITICAL - %s%s%s" % (e.info, e.perf_data, e.addl))
        exit(2)
    except CheckNagiosUnknown as e:
        print("UNKNOWN - %s%s%s" % (e.info, e.perf_data, e.addl))
        exit(3)
    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        print("UNKNOWN - Error: %s at line %s\n%s" % (str(e), tb.tb_lineno, traceback_info.format))
        exit(3)
    print("OK - Data Collected | %s\n%s%s" % \
            (perf_data, out, sys.argv))
    exit(0)

if __name__ == "__main__":
  main(sys.argv)
