import sys, getopt
from .check import SAMMCheck
import etcd
import time
from datetime import datetime, timezone, timedelta
import subprocess
import socket
from sammwr import WMIQuery, WinRMShell
from hashlib import md5, sha256
import re
import json
sys.path.append("/usr/local/nagios/libexec/lib/python3/dist-packages")
from samana.base import auth_file

intstr = lambda x: str(x) if x is not None else ''
gt = lambda x, y: x is not None and y is not None and x > y

queries = {
    'os': "SELECT * FROM Win32_OperatingSystem",
    'disk': "SELECT * FROM Win32_LogicalDisk",
    'cpu': "SELECT * FROM Win32_PerfFormattedData_PerfOS_Processor WHERE Name='_Total'" ,
    'pf': "SELECT * FROM Win32_PageFileUsage",
    'evt_system':
        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d " \
        "and Logfile = 'System'",
    'evt_application':
        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d " \
        "and Logfile = 'Application'",
    'evt_sf':
        "SELECT * FROM Win32_NTLogEvent WHERE TimeGenerated > '%s' and EventType <= %d " \
        "and Logfile = 'Citrix Delivery Services'",
    'proc': 'SELECT * FROM Win32_Process',
    'services': 'SELECT Name, DisplayName, ProcessId, Started, StartName, State, Status ' \
        'FROM Win32_Service',
    'computer': "SELECT * FROM Win32_ComputerSystem"
}

class SAMMWMICheck(SAMMCheck):
    def __init__(self, argv=None, max_age=600, ttl=480, event_secs=300, event_level=2):
        self._etcdserver = "127.0.0.1"
        self._etcdport = 2379
        self._hostid = ""
        self._ttl = ttl
        self._hostaddress = None
        self._hostip = None
        self._username = None
        self._password = None
        self._domain = None
        self._namespace = "root\\cimv2"
        self._warn = None
        self._crit = None
        self._ping_warn = None
        self._ping_crit = None
        self._wmi_warn = None
        self._wmi_crit = None
        self._dns_warn = None
        self._dns_crit = None
        self._packet_loss_warn = None
        self._packet_loss_crit = None
        self._event_level = event_level
        self._event_secs = event_secs
        self._dns_time = 0
        self._ping_time = 0
        self._ping_count = 1

        super().__init__(argv)
        if self.done:
            return self.unknown()

        if self._hostaddress is None:
            return self.unknown("Host Address not specified.")
        if self._username is None:
            return self.unknown("Auth data not defined")

        if self._warn is not None:
            try:
                (self._dns_warn, 
                    self._ping_warn, 
                    self._packet_loss_warn, 
                    self._wmi_warn) = self._warn.split(',')
                dns_warn = int(dns_warn)
                ping_warn = int(ping_warn)
                packet_loss_warn = int(packet_loss_warn)
                wmi_warn = int(wmi_warn)
            except ValueError:
                return self.unknown("Invalid WARNING threshold.")

        if self._crit is not None:
            try:
                (dns_crit, 
                    ping_crit, 
                    packet_loss_crit, 
                    wmi_crit) = self._crit.split(',')
                ping_crit = int(ping_crit)
                packet_loss_crit = int(packet_loss_crit)
                wmi_crit = int(wmi_crit)
            except ValueError:
                return self.unknown("Invalid Critical threshold")
        self.outmsg = "UNKNOWN - Plugin Initialized but not run"
        self._data = None
        self._etcdclient = etcd.Client(host=self._etcdserver, port=self._etcdport)
        self.ready = True
    
    def process_args(self, argv):
        try:
            opts, args = getopt.getopt(argv, "hH:U:p:n:t:w:c:a:e:")
        except getopt.GetoptError as e:
            return self.help(str(e))
        for opt, arg in opts:
            if opt == '-h':
                return self.help()
            elif opt == "-H":
                self._hostaddress = arg
            elif opt == '-U':
                temp = arg.split("\\")
                if len(temp) > 1:
                    self._domain = temp[0]
                    self._username = temp[1]
                else:
                    self._username = arg
            elif opt == '-p':
                self._password = arg
            elif opt == '-n':
                self._namespace = arg
            elif opt == '-t':
                self._ttl = arg
            elif opt == '-w':
                self._warn = arg
            elif opt == '-c':
                self._crit = arg
            elif opt == '-a':
                (self._username, self._password, self._domain) = auth_file(arg)
            elif opt == "-e":
                temp = arg.split(':')
                self._etcdserver = temp[0]
                if len(temp) > 1:
                    try:
                        self._etcdport = int(temp[1])
                    except ValueError:
                        return unknown("Invalid port")
            else:
                return self.help()

    def help(self, msg=""):
        self.outmsg = "%s\n" \
            "Check Samana Etcd v2.0.0\n" \
            "This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of\n" \
            "SAMANA GROUP LLC. If you want to use it, you should contact us before\n" \
            "to get a license.\n" \
            "Copyright (c) 2021 Samana Group LLC\n\n" \
            "Usage: %s  [options]\n" \
            "-H <host name>    Windows Server to be queried\n" \
            "-U <username>     User in Windows Domain (domain\\user) or local Windows user" \
            "-p <password>     User's password\n" \
            "-a <auth file>    File containing credentials. In the file, username cannot be UPN.\n" \
            "-n <namespace>    WMI namespace, default root\\cimv2\n" \
            "-w <warning>      Warning threshold."\
            "                  Format: <dns warn secs>,<ping warn secs>,<packets lost warn>,<wmi warn secs>\n" \
            "-c <critical>     Critical threshold\n" \
            "                  Format: <dns crit secs>,<ping crit secs>,<packets lost crit>,<wmi crit secs>\n" \
            "-e <etcd server>  Etcd server IP/Hostname and port. Default value 127.0.0.1:2379\n" \
            "-t <ttl>          Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds\n" \
            "-h                To get this help message\n" \
            "%s" % (msg, sys.argv[0], ' '.join(sys.argv))
        self.outval = 3
        self.done = True
        self.stop = time.time

    def run(self):
        if not self.ready: return
        self.start = time.time()
        self.running = True
        addl=""
        if not self.get_dns_ip():
            return
        
        if not self.ping_host():
            return

        ct = datetime.now(timezone.utc) - timedelta(seconds=self._event_secs)
        timefilter = ct.strftime("%Y%m%d%H%M%S.000-000")

        filter_tuples = {
            'evt_application': (timefilter, 2),
            'evt_system': (timefilter, 2),
            'evt_sf': (timefilter, 2)
        }
        wmi_start = time.time()
        if not self.query_server(filter_tuples=filter_tuples):
            return
        self._wmi_time = int((time.time() - wmi_start) * 1000)
        self.legacy()
        self._data['classes'] = {
            'Win32_OperatingSystem': self._server['os'],
            'Win32_LogicalDisk': self._server['disk'],
            'Win32_PerfFormattedData_PerfOS_Processor': self._server['cpu'],
            'Win32_PageFileUsage': self._server['pf'],
            'Win32_ComputerSystem': self._server['computer']
        }

        c = etcd.Client(host=self._etcdserver, port=int(self._etcdport))
        c.set("samanamonitor/data/%s" % self._data['ID'], json.dumps(self._data), 
            self._ttl)

        perf_data = " | pullinfo.dns_resolution=%d;%s;%s;0;" % (
            int(self._dns_time), 
            intstr(self._dns_warn), 
            intstr(self._dns_crit))
        perf_data += " pullinfo.ping_perc_packet_loss=%d;%s;%s;0;100" % (
            int(self._perc_packet_loss),
            intstr(self._packet_loss_warn),
            intstr(self._packet_loss_crit))
        perf_data += " pullinfo.ping_rtt=%d;%s;%s;0;" % (
            int(self._ping_avg),
            intstr(self._ping_warn),
            intstr(self._ping_crit))
        perf_data += " pullinfo.wmi_time=%d;%s;%s;0;" % (
            int(self._wmi_time),
            intstr(self._wmi_warn),
            intstr(self._wmi_crit))

        if gt(self._dns_time, self._dns_crit):
            self.critical("DNS name resolution took longer than expected %d" \
                    % self._dns_time, perf_data=perf_data, addl=addl)
            return
        if gt(self._ping_avg, self._ping_crit):
            self.critical("PING rtt is greater than expected %d ms" \
                    % self._ping_avg, perf_data=perf_data, addl=addl)
            return
        if gt(self._perc_packet_loss, self._packet_loss_crit):
            self.critical("PING lost %d%% packets" \
                    % perc_packet_loss, perf_data=perf_data, addl=addl)
            return

        if gt(self._wmi_time, self._wmi_crit):
            self.critical("WMI took longer than expected %d ms" \
                    % wmi_time, perf_data=perf_data, addl=addl)
            return

        if gt(self._dns_time, self._dns_warn):
            self.warning("DNS name resolution took longer than expected %d" \
                    % self._dns_time, perf_data=perf_data, addl=addl)
            return

        if gt(self._ping_avg, self._ping_warn):
            self.warning("PING rtt is greater than expected %d ms" \
                    % self._ping_avg, perf_data=perf_data, addl=addl)
            return

        if gt(self._perc_packet_loss, self._packet_loss_warn):
            self.warning("PING lost %d%% packets" \
                    % perc_packet_loss, perf_data=perf_data, addl=addl)
            return

        if gt(self._wmi_time, self._wmi_warn):
            self.warning("WMI took longer than expected %d ms" \
                    % wmi_time, perf_data=perf_data, addl=addl)
            return

        self.ok("OK - Data Collected. ID: %s" \
            % self._data['ID'], perf_data=perf_data, addl=addl)

    def ping_host(self):
        p = subprocess.Popen(["ping", "-c", str(self._ping_count), 
                self._hostaddress], stdout = subprocess.PIPE)
        out = p.communicate()
        if p.returncode != 0:
            self.critical("Server is %s not responding" % ip)
            return False

        packets = None
        rtt = None
        try:
            outstr = out[0].decode('utf8')
            pat = re.search("^(\d+) packets transmitted, (\d+) (packets )?received", 
                outstr, flags=re.M)
            if pat is None:
                raise ValueError("Cannot extract packets from ping output.")
            packets = pat.groups()
            packets_sent = int(packets[0])
            packets_received = int(packets[1])
            self._perc_packet_loss = 100-int(100.0 * packets_received / packets_sent)

            pat = re.search("^(round-trip|rtt) min/avg/max/(stddev|mdev) = " \
                "([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)",
                outstr, flags=re.M)
            if pat is None:
                raise ValueError("Cannot extract ping rtt times.")
            rtt = pat.groups()
            self._ping_avg = int(float(rtt[3]))

        except (ValueError, IndexError) as e:
            self.unknown("Ping output invalid", addl="%s\n%s" % (str(e), outstr))
            return False
        except Exception as e:
            self.unknown("Unexpected Error", addl="%s\n%s\n%s\n%s" % 
                (str(e), outstr, packets, rtt))
            return False
        return True

    def get_dns_ip(self):
        pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        if pat.match(self._hostaddress):
            return (self._hostaddress, 0)

        try:
            dns_start = time.time()
            server_data = socket.gethostbyname_ex(self._hostaddress)
            ips = server_data[2]
            if not isinstance(ips, list) and len(ips) != 1:
                self.unknown("hostname is linked to more than 1 IP or 0 IPs")
                return False
            self._dns_time = int((time.time() - dns_start) * 1000)
            self._hostip = ips[0]

        except ValueError as err:
            self.unknown("%s" % str(err))
            return False
        except IndexError as err:
            self.unknown("Invalid data received from gethostbyname_ex\n%s" % str(err))
            return False
        except Exception as err:
            self.unknown("Unable to resove hostname to IP address\n%s" % str(err))
            return False
        return True

    def query_server(self, filter_tuples={}):
        ''' param:filter_tuples is a dictionary where keys matches the 
            key in queries global dictionary if the key doesn't exist, then an
            empty tuple is expected, otherwise the tuple must contain all
            the arguments needed to complete the string
        '''
        self._server = {}
        #shell = WinRMShell()
        #shell.open(self._hostip, {
        #    'username': self._username,
        #    'password': self._password,
        #    'domain': self._domain})
        #if shell.connected != True:
        #    self.unknown("Unable to connecto to server. Error %s" % conn_status)
        #    return False
        q = WMIQuery(endpoint="http://%s:5985/wsman" % self._hostip,
            username=self._username,
            password=self._password)
        for i in queries.keys():
            try:
                self._server[i] = q.wql(queries[i] % filter_tuples.get(i, ()))
            except Exception as e:
                self._server[i] = [None]
            if not isinstance(self._server[i], list):
                self.unknown("Error connecting to server %s" % i)
                return False
        return True

    def legacy(self):
        computer = self._server['computer'][0]
        cpu = self._server['cpu'][0]
        os = self._server['os'][0]
        TotalSwapSpaceSize = 0
        for i in self._server['pf']:
            TotalSwapSpaceSize += int(i['AllocatedBaseSize'])

        t = os['LastBootUpTime']['Datetime'][:-6]
        tzmin = (int(os['LastBootUpTime']['Datetime'][-6:-3])*60 + \
                int(os['LastBootUpTime']['Datetime'][-2:])) * \
                1 if os['LastBootUpTime']['Datetime'][-6] == '-' else -1
        st = datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%f") + \
            timedelta(minutes=tzmin)
        uptimehrs = int((datetime.utcnow()- st).total_seconds() / 60 / 60)
        fqdn = "%s.%s" % (computer['DNSHostName'], computer['Domain'])
        fqdn = fqdn.lower()
        serverid = fqdn

        self._data = {
            'epoch': int(time.time()),
            'DNSHostName': computer['DNSHostName'],
            'Domain': computer['Domain'],
            'ID': serverid,
            'PercentIdleTime': int(cpu['PercentIdleTime']),
            'PercentInterruptTime': int(cpu['PercentInterruptTime']),
            'PercentPrivilegedTime': int(cpu['PercentPrivilegedTime']),
            'PercentProcessorTime': int(cpu['PercentProcessorTime']),
            'PercentUserTime': int(cpu['PercentUserTime']),
            'FreePhysicalMemory': int(os['FreePhysicalMemory']),
            'FreeSpaceInPagingFiles': int(os['FreeSpaceInPagingFiles'])/1024,
            'FreeVirtualMemory': int(os['FreeVirtualMemory']),
            'TotalSwapSpaceSize': int(TotalSwapSpaceSize),
            'TotalVirtualMemorySize': int(os['TotalVirtualMemorySize']),
            'TotalVisibleMemorySize': int(os['TotalVisibleMemorySize']),
            'NumberOfProcesses': int(os['NumberOfProcesses']),
            'LastBootUpTime': os['LastBootUpTime'],
            'UpTime': uptimehrs,
            'Disks': [],
            'Services': [],
            'Events': {
                'System': [],
                'Application': [],
                'Citrix Delivery Services': []
            }
        }
        for s in self._server['services']:
            s['ServiceName'] = s.get('Name')
            self._data['Services'].append(s)
        for e in self._server['evt_system']:
            self._data['Events']['System'].append(e)
        for e in self._server['evt_application']:
            self._data['Events']['Application'].append(e)
        for e in self._server['evt_sf']:
            self._data['Events']['Citrix Delivery Services'].append(e)
        for d in self._server['disk']:
            self._data['Disks'].append(d)
