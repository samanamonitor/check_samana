#!/usr/bin/python3

import time
import json
import csv
import sys, getopt
import traceback
from samana.nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
from samana.base import get_dns_ip, ping_host, perf, auth_file

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
    'services': 'SELECT Name, DisplayName, ProcessId, Started, StartName, State, Status FROM Win32_Service',
    'computer': "SELECT * FROM Win32_ComputerSystem"
}

def usage():
  return """Check WMI v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2021 Samana Group LLC

Usage:
  %s -H <host name> ( -U <username> -p <password> ) [-i <id type>] [-n <namespace>] [-e <etcd server>] [-m <memcache server>] [-t <ttl>] [ -w dnswarn,pingwarn,packetlosswarn,wmiwarn ] [ -c dnscrit,pingcrit,packetlosscrit,wmicrit ]

  <host name>        Windows Server to be queried
  <username>         User in Windows Domain (domain\\user) or local Windows user
  <password>         User password
  <id type>          Id encoding, can be one of "md5", "sha256" or "fqdn". Default is "md5"
  <namespace>        WMI namespace, default root\\cimv2
  <etcd server>      Etcd server IP/Hostname and port(optional). Default value 127.0.0.1:2379
  <memcache server>  Memcached server IP/Hostname and port(optional). Format <server ip/hostname>:11211. If set, etcd will not be used.
  <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
""" % sys.argv[0] if len(sys.argv) > 0 else "???????"


def query_server(host, username, password, namespace="root\\cimv2", filter_tuples={}):
    ''' param:filter_tuples is a dictionary where keys matches the key in queries global dictionary
        if the key doesn't exist, then an empty tuple is expected, otherwise the tuple
        must contain all the arguments needed to complete the string
    '''
    import pywmi
    server = {}
    conn_status = pywmi.open(host, username, password, namespace)
    if conn_status != 0:
        raise CheckUnknown("Unable to connecto to server. Error %s" % conn_status)
    for i in queries.keys():
        server[i] = pywmi.query(queries[i] % filter_tuples.get(i, ()))
        if not isinstance(server[i], list):
            pywmi.close()
            raise CheckUnknown("Error connecting to server %08x" % server[i])
    pywmi.close()
    return server

def legacy(indata, idtype='md5'):
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
    fqdn = computer['DNSHostName'], computer['Domain']
    if idtype == 'md5':
        serverid = md5(fqdn).hexdigest().upper()
    elif idtype == 'sha256':
        serverid = sha256(fqdn).hexdigest().upper()
    elif idtype == 'fqdn':
        serverid = fqdn
    else:
        raise CheckUnknown("Invalid id type %s" % idtype)

    return {
        'epoch': int(time.time()),
        'DNSHostName': computer['DNSHostName'],
        'Domain': computer['Domain'],
        'ID': serverid,
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

def main(argv):
    try:
        etcdserver = '127.0.0.1'
        etcdport = '2379'
        memcacheserver = '127.0.0.1'
        memcacheport = '11211'
        cachetype = 'etcd'
        opts, args = getopt.getopt(sys.argv[1:], "H:he:t:U:p:n:w:c:m:a:")
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
        idtype = "md5"

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
            elif o == '-m':
                cachetype = 'memcache'
                temp = a.split(':')
                memcacheserver = temp[0]
                if len(temp) > 1:
                    memcacheport = temp[1]
            elif o == '-t':
                ttl = a
            elif o == '-w':
                warning = a
            elif o == '-c':
                critical = a
            elif o == '-a':
                (username, password, domain) = auth_file(a)
                if domain is not None:
                    username = "%s\\%s" % (domain, username)
            elif o == "-i":
                idtype = a
            elif o == '-h':
                raise CheckUnknown("Help", addl=usage())
            else:
                raise CheckUnknown("Unknown Argument", addl=usage())

        if hostaddress is None:
            raise CheckUnknown("Host Address not defined")
        if username is None:
            raise CheckUnknown("Auth data not defined")

        if warning is not None:
            try:
                (dns_warn, ping_warn, packet_loss_warn, wmi_warn) = warning.split(',')
                dns_warn = int(dns_warn)
                ping_warn = int(ping_warn)
                packet_loss_warn = int(packet_loss_warn)
                wmi_warn = int(wmi_warn)
            except ValueError:
                raise CheckUnknown("Invalid Warning values")

        if critical is not None:
            try:
                (dns_crit, ping_crit, packet_loss_crit, wmi_crit) = critical.split(',')
                ping_crit = int(ping_crit)
                packet_loss_crit = int(packet_loss_crit)
                wmi_crit = int(wmi_crit)
            except ValueError:
                raise CheckUnknown("Invalid Critical values")

        (hostip, dns_time) = get_dns_ip(hostaddress)
        ping_data = ping_host(hostip)
        perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])

        wmi_start = time.time()
        ct = time.strptime(time.ctime(time.time() - event_secs))
        timefilter = "%04d%02d%02d%02d%02d%02d.000-000" % (ct.tm_year, ct.tm_mon, ct.tm_mday, ct.tm_hour, ct.tm_min, ct.tm_sec)

        filter_tuples = {
            'evt_application': (timefilter, 2),
            'evt_system': (timefilter, 2),
            'evt_sf': (timefilter, 2)
        }
        a = query_server(hostaddress, username, password, namespace=namespace, filter_tuples=filter_tuples)
        data = legacy(a, idtype)
        wmi_time = int((time.time() - wmi_start) * 1000)

        if cachetype == 'etcd':
            from samana import etcd
            c = etcd.Client(host=etcdserver, port=etcdport)
            c.put("samanamonitor/data/%s" % data['ID'].lower(), json.dumps(data), ttl)
        elif cachetype == 'memcache':
            import memcache
            mc = memcache.Client(['%s:%s' % (memcacheserver, memcacheport)], debug=0)
            mckey = "samanamonitor/data/%s" % data['ID'].lower()
            val = json.dumps(data)
            mc.set(mckey, val, time=ttl)
            print(mckey, len(val), ttl)
        else:
            raise CheckUnknown("Invalid cache type")
            

        perf_data = " ".join([
            perf('dns_resolution', dns_time, dns_warn, dns_crit),
            perf('ping_perc_packet_loss', perc_packet_loss, packet_loss_warn, packet_loss_crit),
            perf('ping_rtt', ping_data['avg'], ping_warn, ping_crit),
            perf('wmi_time', wmi_time, wmi_warn, wmi_crit)])

        notnone_and_lt = lambda x, y: True if x is not None and int(x) < y else False

        if notnone_and_lt(dns_crit, dns_time):
            raise CheckNagiosCritical("DNS name resolution took longer than expected %d" % dns_time, perf_data=perf_data)
        if notnone_and_lt(dns_warn, dns_time):
            raise CheckNagiosWarning("DNS name resolution took longer than expected %d" % dns_time, perf_data=perf_data)
        if notnone_and_lt(packet_loss_crit, perc_packet_loss):
            raise CheckNagiosCritical("PING lost %d%% packets" % perc_packet_loss, perf_data=perf_data)
        if notnone_and_lt(packet_loss_warn, perc_packet_loss):
            raise CheckNagiosWarning("PING lost %d%% packets" % perc_packet_loss, perf_data=perf_data)
        if notnone_and_lt(ping_crit, ping_data['avg']):
            raise CheckNagiosCritical("PING rtt is greater than expected %d ms" % ping_data['avg'], perf_data=perf_data)
        if notnone_and_lt(ping_warn, ping_data['avg']):
            raise CheckNagiosWarning("PING rtt is greater than expected %d ms" % ping_data['avg'], perf_data=perf_data)
        if notnone_and_lt(wmi_crit, wmi_time):
            raise CheckNagiosCritical("WMI took longer than expected %d ms" % wmi_time, perf_data=perf_data)
        if notnone_and_lt(wmi_warn, wmi_time):
            raise CheckNagiosWarning("WMI took longer than expected %d ms" % wmi_time, perf_data=perf_data)

        out = CheckResult("Data Collected", perf_data=perf_data, addl=' '.join(sys.argv))
    except CheckWarning as e:
        out = e.result
    except CheckCritical as e:
        out = e.result
    except CheckUnknown as e:
        out = e.result
    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        out = CheckResult("Error: %s at line %s" % (str(e), tb.tb_lineno), addl=traceback_info.format, status=3, status_str="UNKNOWN")

    print(out)
    exit(out.status)

if __name__ == "__main__":
  main(sys.argv)
