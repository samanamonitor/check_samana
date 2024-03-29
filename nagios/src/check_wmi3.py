#!/usr/bin/python3

import sys
sys.path.append('/usr/local/nagios/libexec/lib/python3/dist-packages')
from sammcheck import SAMMWMICheck

if __name__ == "__main__":
    check = SAMMWMICheck(sys.argv[1:])
    check.run()
    print(check)
    exit(check.outval)


#import sys, getopt
#sys.path.append('/usr/local/nagios/libexec/lib/python3/dist-packages')
#import time
#from datetime import datetime, timezone, timedelta
#import json
#import csv
#import traceback
#from samana.nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
#from samana.base import get_dns_ip, ping_host, perf, auth_file
#from sammwr import WMIQuery, WinRMShell
#
#event_level = 2
#event_secs = 300
#default_ttl = 480
#
#queries = {
#    'os': "SELECT * FROM Win32_OperatingSystem",
#    'disk': "SELECT * FROM Win32_LogicalDisk",
#    'cpu': "SELECT * FROM Win32_PerfFormattedData_PerfOS_Processor WHERE Name='_Total'" ,
#    'pf': "SELECT * FROM Win32_PageFileUsage",
#    'evt_system':
#        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'System'",
#    'evt_application':
#        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'Application'",
#    'evt_sf':
#        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d and Logfile = 'Citrix Delivery Services'",
#    'proc': 'SELECT * FROM Win32_Process',
#    'services': 'SELECT Name, DisplayName, ProcessId, Started, StartName, State, Status FROM Win32_Service',
#    'computer': "SELECT * FROM Win32_ComputerSystem"
#}
#
#def usage():
#  return """Check WMI v1.0.0
#This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
#SAMANA GROUP LLC. If you want to use it, you should contact us before
#to get a license.
#Copyright (c) 2021 Samana Group LLC
#
#Usage:
#  %s -H <host name> ( -U <username> -p <password> | -a <auth file>) [-i <id type>] [-n <namespace>] [-e <etcd server>] [-m <memcache server>] [-t <ttl>] [ -w dnswarn,pingwarn,packetlosswarn,wmiwarn ] [ -c dnscrit,pingcrit,packetlosscrit,wmicrit ]
#
#  <host name>        Windows Server to be queried
#  <username>         User in Windows Domain (domain\\user) or local Windows user
#  <password>         User password
#  <auth file>        File containing credentials. In the file, username cannot be UPN.
#  <id type>          Id encoding, can be one of "md5", "sha256" or "fqdn". Default is "md5"
#  <namespace>        WMI namespace, default root\\cimv2
#  <etcd server>      Etcd server IP/Hostname and port(optional). Default value 127.0.0.1:2379
#  <memcache server>  Memcached server IP/Hostname and port(optional). Format <server ip/hostname>:11211. If set, etcd will not be used.
#  <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
#""" % sys.argv[0] if len(sys.argv) > 0 else "???????"
#
#
#def query_server(host, username, password, domain, namespace="root\\cimv2", filter_tuples={}):
#    ''' param:filter_tuples is a dictionary where keys matches the key in queries global dictionary
#        if the key doesn't exist, then an empty tuple is expected, otherwise the tuple
#        must contain all the arguments needed to complete the string
#    '''
#    server = {}
#    shell = WinRMShell()
#    shell.open(host, {'username': username, 'password': password, 'domain': domain})
#    if shell.connected != True:
#        raise CheckUnknown("Unable to connecto to server. Error %s" % conn_status)
#    q = WMIQuery(shell)
#    for i in queries.keys():
#        try:
#            server[i] = q.wql(queries[i] % filter_tuples.get(i, ()))
#        except:
#            server[i] = [{}]
#        if not isinstance(server[i], list):
#            shell.close()
#            raise CheckUnknown("Error connecting to server %08x" % server[i])
#    shell.close()
#    return server
#
#def legacy(indata, idtype='md5'):
#    from hashlib import md5, sha256
#
#    computer = indata['computer'][0]
#    cpu = indata['cpu'][0]
#    os = indata['os'][0]
#    TotalSwapSpaceSize = 0
#    for i in indata['pf']:
#        TotalSwapSpaceSize += int(i['AllocatedBaseSize'])
#
#    t = os['LastBootUpTime']['Datetime'][:-6]
#    tzmin = (int(os['LastBootUpTime']['Datetime'][-6:-3])*60 + \
#            int(os['LastBootUpTime']['Datetime'][-2:])) * \
#            1 if os['LastBootUpTime']['Datetime'][-6] == '-' else -1
#    st = datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%f") + \
#        timedelta(minutes=tzmin)
#    uptimehrs = int((datetime.utcnow()- st).total_seconds() / 60 / 60)
#    fqdn = "%s.%s" % (computer['DNSHostName'], computer['Domain'])
#    fqdn = fqdn.lower()
#    if idtype == 'md5':
#        serverid = md5(fqdn.encode("utf8")).hexdigest().upper()
#    elif idtype == 'sha256':
#        serverid = sha256(fqdn.encode("utf8")).hexdigest().upper()
#    elif idtype == 'fqdn':
#        serverid = fqdn
#    else:
#        raise CheckUnknown("Invalid id type %s" % idtype)
#
#    ret = {
#        'epoch': int(time.time()),
#        'DNSHostName': computer['DNSHostName'],
#        'Domain': computer['Domain'],
#        'ID': serverid,
#        'PercentIdleTime': int(cpu['PercentIdleTime']),
#        'PercentInterruptTime': int(cpu['PercentInterruptTime']),
#        'PercentPrivilegedTime': int(cpu['PercentPrivilegedTime']),
#        'PercentProcessorTime': int(cpu['PercentProcessorTime']),
#        'PercentUserTime': int(cpu['PercentUserTime']),
#        'FreePhysicalMemory': int(os['FreePhysicalMemory']),
#        'FreeSpaceInPagingFiles': int(os['FreeSpaceInPagingFiles'])/1024,
#        'FreeVirtualMemory': int(os['FreeVirtualMemory']),
#        'TotalSwapSpaceSize': int(TotalSwapSpaceSize),
#        'TotalVirtualMemorySize': int(os['TotalVirtualMemorySize']),
#        'TotalVisibleMemorySize': int(os['TotalVisibleMemorySize']),
#        'NumberOfProcesses': int(os['NumberOfProcesses']),
#        'LastBootUpTime': os['LastBootUpTime'],
#        'UpTime': uptimehrs,
#        'Disks': [],
#        'Services': [],
#        'Events': {
#            'System': [],
#            'Application': [],
#            'Citrix Delivery Services': []
#        }
#    }
#    for s in indata['services']:
#        s['ServiceName'] = s.get('Name')
#        ret['Services'].append(s)
#    for e in indata['evt_system']:
#        ret['Events']['System'].append(e)
#    for e in indata['evt_application']:
#        ret['Events']['Application'].append(e)
#    for e in indata['evt_sf']:
#        ret['Events']['Citrix Delivery Services'].append(e)
#    for d in indata['disk']:
#        ret['Disks'].append(d)
#
#    return ret
#
#def main(argv):
#    etcdserver = '127.0.0.1'
#    etcdport = '2379'
#    memcacheserver = '127.0.0.1'
#    memcacheport = '11211'
#    cachetype = 'etcd'
#    ttl = default_ttl
#    hostaddress = None
#    username = None
#    password = None
#    domain = None
#    namespace = "root\\cimv2"
#    url = None
#    warning = None
#    critical = None
#    ping_warn = None
#    ping_crit = None
#    wmi_warn = None
#    wmi_crit = None
#    dns_warn = None
#    dns_crit = None
#    packet_loss_warn = None
#    packet_loss_crit = None
#    idtype = "fqdn"
#    try:
#        opts, args = getopt.getopt(sys.argv[1:], "H:he:t:U:p:n:w:c:m:a:i:N:")
#
#        for o, a in opts:
#            if o == '-H':
#                hostaddress = a
#            elif o == '-U':
#                temp = a.split("\\")
#                if len(temp) > 1:
#                    domain = temp[0]
#                    username = temp[1]
#                else:
#                    username = a
#            elif o == '-p':
#                password = a
#            elif o == 'n':
#                namespace = a
#            elif o == '-e':
#                if a[:7] == "http://":
#                    a = a[7:]
#                temp = a.split(':')
#                etcdserver =temp[0]
#                if len(temp) > 1:
#                    etcdport = temp[1]
#            elif o == '-m':
#                cachetype = 'memcache'
#                temp = a.split(':')
#                memcacheserver = temp[0]
#                if len(temp) > 1:
#                    memcacheport = temp[1]
#            elif o == '-t':
#                ttl = a
#            elif o == '-w':
#                warning = a
#            elif o == '-c':
#                critical = a
#            elif o == '-a':
#                (username, password, domain) = auth_file(a)
#            elif o == "-i":
#                idtype = a
#            elif o == "-N":
#                pass
#            elif o == '-h':
#                raise CheckUnknown("Help", addl=usage())
#            else:
#                raise CheckUnknown("Unknown Argument", addl=usage())
#
#        if hostaddress is None:
#            raise CheckUnknown("Host Address not defined")
#        if username is None:
#            raise CheckUnknown("Auth data not defined")
#
#        if warning is not None:
#            try:
#                (dns_warn, ping_warn, packet_loss_warn, wmi_warn) = warning.split(',')
#                dns_warn = int(dns_warn)
#                ping_warn = int(ping_warn)
#                packet_loss_warn = int(packet_loss_warn)
#                wmi_warn = int(wmi_warn)
#            except ValueError:
#                raise CheckUnknown("Invalid Warning values")
#
#        if critical is not None:
#            try:
#                (dns_crit, ping_crit, packet_loss_crit, wmi_crit) = critical.split(',')
#                ping_crit = int(ping_crit)
#                packet_loss_crit = int(packet_loss_crit)
#                wmi_crit = int(wmi_crit)
#            except ValueError:
#                raise CheckUnknown("Invalid Critical values")
#
#        (hostip, dns_time) = get_dns_ip(hostaddress)
#        ping_data = ping_host(hostip)
#        perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])
#
#        wmi_start = time.time()
#
#        ct = datetime.now(timezone.utc) - timedelta(seconds=event_secs)
#        timefilter = ct.strftime("%Y%m%d%H%M%S.000-000")
#
#        filter_tuples = {
#            'evt_application': (timefilter, 2),
#            'evt_system': (timefilter, 2),
#            'evt_sf': (timefilter, 2)
#        }
#        a = query_server(hostip, username, password, domain, namespace=namespace, filter_tuples=filter_tuples)
#        data = legacy(a, idtype)
#        wmi_time = int((time.time() - wmi_start) * 1000)
#        data['classes'] = {
#            'Win32_OperatingSystem': a['os'],
#            'Win32_LogicalDisk': a['disk'],
#            'Win32_PerfFormattedData_PerfOS_Processor': a['cpu'],
#            'Win32_PageFileUsage': a['pf'],
#            'Win32_ComputerSystem': a['computer']
#        }
#
#        if cachetype == 'etcd':
#            if sys.version_info.major == 3:
#                from samana import etcd
#            else:
#                import etcd
#            c = etcd.Client(host=etcdserver, port=int(etcdport))
#            c.set("samanamonitor/data/%s" % data['ID'], json.dumps(data), ttl)
#        elif cachetype == 'memcache':
#            import memcache
#            mc = memcache.Client(['%s:%s' % (memcacheserver, memcacheport)], debug=0)
#            mckey = "samanamonitor/data/%s" % data['ID']
#            val = json.dumps(data)
#            mc.set(mckey, val, time=ttl)
#            print(mckey, len(val), ttl)
#        else:
#            raise CheckUnknown("Invalid cache type")
#            
#
#        perf_data = " ".join([
#            perf('pullinfo.dns_resolution', dns_time, dns_warn, dns_crit),
#            perf('pullinfo.ping_perc_packet_loss', perc_packet_loss, packet_loss_warn, packet_loss_crit),
#            perf('pullinfo.ping_rtt', ping_data['avg'], ping_warn, ping_crit),
#            perf('pullinfo.wmi_time', wmi_time, wmi_warn, wmi_crit)])
#
#        notnone_and_lt = lambda x, y: True if x is not None and int(x) < y else False
#
#        if notnone_and_lt(dns_crit, dns_time):
#            raise CheckCritical("DNS name resolution took longer than expected %d" % dns_time, perf_data=perf_data)
#        if notnone_and_lt(dns_warn, dns_time):
#            raise CheckNagiosWarning("DNS name resolution took longer than expected %d" % dns_time, perf_data=perf_data)
#        if notnone_and_lt(packet_loss_crit, perc_packet_loss):
#            raise CheckCritical("PING lost %d%% packets" % perc_packet_loss, perf_data=perf_data)
#        if notnone_and_lt(packet_loss_warn, perc_packet_loss):
#            raise CheckNagiosWarning("PING lost %d%% packets" % perc_packet_loss, perf_data=perf_data)
#        if notnone_and_lt(ping_crit, ping_data['avg']):
#            raise CheckCritical("PING rtt is greater than expected %d ms" % ping_data['avg'], perf_data=perf_data)
#        if notnone_and_lt(ping_warn, ping_data['avg']):
#            raise CheckNagiosWarning("PING rtt is greater than expected %d ms" % ping_data['avg'], perf_data=perf_data)
#        if notnone_and_lt(wmi_crit, wmi_time):
#            raise CheckCritical("WMI took longer than expected %d ms" % wmi_time, perf_data=perf_data)
#        if notnone_and_lt(wmi_warn, wmi_time):
#            raise CheckWarning("WMI took longer than expected %d ms" % wmi_time, perf_data=perf_data)
#
#        out = CheckResult("Data Collected. ID: %s" % data['ID'], perf_data=perf_data, addl=' '.join(sys.argv))
#    except CheckWarning as e:
#        out = e.result
#    except CheckCritical as e:
#        out = e.result
#    except CheckUnknown as e:
#        out = e.result
#    except Exception as e:
#        exc_type, exc_obj, tb = sys.exc_info()
#        traceback_info = traceback.extract_tb(tb)
#        out = CheckResult("Error: %s at line %s" % (str(e), tb.tb_lineno), addl=traceback_info, status=3, status_str="UNKNOWN")
#
#    print(out)
#    return out.status
#
#if __name__ == "__main__":
#  exit(main(sys.argv))
#