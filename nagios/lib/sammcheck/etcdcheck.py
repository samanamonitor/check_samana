import sys, getopt
from .check import SAMMCheck
import json
import re
import etcd
import time

intstr = lambda x: str(x) if x is not None else ''
class SAMMEtcdCheck(SAMMCheck):
    def __init__(self, argv=None, max_age=600):
        self._etcdserver = "127.0.0.1"
        self._etcdport = 2379
        self._crit = None
        self._warn = None
        self._hostid = ""
        self._excl = None
        self._submod = None
        self._logfilters = []
        self._module = None

        super().__init__(argv)
        if self.done:
            return self.unknown()
        self._max_age = max_age

        if self._hostid == "":
            return self.unknown("Host ID not specified.")

        if self._crit is not None:
            try:
                self._crit = int(self._crit)
            except:
                return self.unknown("Invalid CRITICAL threshold.")

        if self._warn is not None:
            try:
                self._warn = int(self._warn)
            except:
                return self.unknown("Invalid WARNING threshold.")

        if self._module is None:
            return self.unknown("Module is a mandatory parameter.")

        self._data = None
        self._etcdclient = etcd.Client(host=self._etcdserver, port=self._etcdport)
        self.ready = True

    def process_args(self, argv):
        try:
            opts, args = getopt.getopt(argv, "hH:m:c:w:s:i:e:x:E:")
        except getopt.GetoptError:
            return self.help()
        
        for opt, arg in opts:
            if opt == '-h':
                return self.help()
            elif opt == "-H":
                self._hostid = arg
            elif opt == "-m":
                self._module = arg
            elif opt == "-c":
                self._crit = arg
            elif opt == "-w":
                self._warn = arg
            elif opt == "-s":
                self._submod = arg
            elif opt == "-i":
                self._incl = arg
            elif opt == "-e":
                self._excl = arg
            elif opt == "-x":
                for f in arg.split(";"):
                    logfilter = tuple(f.split(','))
                    if len(logfilter) < 2:
                        logfilter += tuple('')
                    self._logfilters += logfilter
            elif opt == "-E":
                temp = arg.split(':')
                self._etcdserver = temp[0]
                if len(temp) > 1:
                    self._etcdport = int(temp[1])
            else:
                return self.help()

    def help(msg=""):
        self.outmsg =  "%s\n" \
            "Check Samana Etcd v2.0.0\n" \
            "This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of\n" \
            "SAMANA GROUP LLC. If you want to use it, you should contact us before\n" \
            "to get a license.\n" \
            "Copyright (c) 2021 Samana Group LLC\n\n" \
            "Usage: %s  [options]\n" \
            "-H <hostid>     Id of the host in Etcd database\n" \
            "-m <module>     Module to query. (cpu|ram|swap|log|services|hddrives|uptime)\n" \
            "-s <logname>    Log name when using \"log\" module.\n" \
            "-w <warning>    Warning threshold\n" \
            "-c <critical>   Critical threshold\n" \
            "-i <include>    Regex of the services that need to be included when using the \"services\" module.\n" \
            "-e <exclude>    Regex of the services that need to be excluded when using the \"services\" module.\n" \
            "-x <logfilter>  When using \"log\" module, this attribute is used to filter out events. the format is:\n" \
            "                logfilter format:  <eventid>,<text>;<eventid>,text;....\n" \
            "                Multiple filters must be separated by ';'\n" \
            "-h              To get this help message\n" \
            "%s" % (msg, sys.argv[0], ' '.join(sys.argv))
        self.outval = 3
        self.done = True
        self.stop = time.time

    def run(self):
        if not self.ready: return
        self.start = time.time()
        self.running = True
        try:
            self._data = json.loads(self._etcdclient.get("/samanamonitor/data/%s" % self._hostid).value)
        except IndexError as e:
            return self.unknown(str(e))
        except etcd.EtcdKeyNotFound:
            return self.unknown("ServerID \"%s\" not found in the database." % self._hostid)
        except ValueError:
            return self.unknown("Data for ServerID \"%s\" is corrupt." % self._hostid)
        except etcd.EtcdException as e:
            return self.unknown("Server \"%s\" not responding." % str(e))

        age_secs = time.time() - self._data['epoch']
        if age_secs > self._max_age:
            return self.unknown("Data is too old %d seconds." % age_secs)

        if 'classes' not in self._data:
            return self.unknown("Legacy check configured.")
            
        if self._module == 'cpu':
            self.cpu()
        elif self._module == 'ram':
            self.ram()
        elif self._module == 'swap':
            self.swap()
        elif self._module == 'log':
            self.log()
        elif self._module == 'services':
            self.services()
        elif self._module == 'hddrives':
            self.hddrives()
        elif self._module == 'uptime':
            self.uptime()
        else:
            self.outmsg = "UNKNOWN - Invalid Module %s" % self._module
            self.outval = 3
        self.done = True
        self.running = False
        self.stop = time.time()

    def cpu(self):
        if self._data is None:
            raise Exception("Data has not been fetched.")
        state = "UNKNOWN"
        graphmax = 100

        val = 100.0 - float(self._data['PercentIdleTime'])

        if self._crit is not None and val > self._crit:
            state = "CRITICAL"
            self.outval = 2
        elif self._warn is not None and val > self._warn:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0
        Processor=self._data['classes']['Win32_PerfFormattedData_PerfOS_Processor'][0]
        perfusage = "| Load=%d;%s;%s;0;%d" % (
            int(val), 
            intstr(self._warn), 
            intstr(self._crit), 
            graphmax)
        perfusage += " PercentIdleTime=%d;;;0;100" % int(Processor['PercentIdleTime'])
        perfusage += " PercentUserTime=%d;;;0;100" % int(Processor['PercentUserTime'])
        perfusage += " PercentPrivilegedTime=%d;;;0;100" % int(Processor['PercentPrivilegedTime'])
        perfusage += " PercentInterruptTime=%d;;;0;100" % int(Processor['PercentInterruptTime'])
        self.outmsg = "%s - CPU Usage %0.f %% %s" % (
            state, val, perfusage)

    def ram(self):
        state = "UNKNOWN"
        
        total = float(self._data['TotalVisibleMemorySize']) / 1024.0
        free = float(self._data['FreePhysicalMemory']) / 1024.0
        used = total - free
        percused = used * 100.0 / total
        percfree = free * 100.0 / total

        if self._crit is not None and percused > self._crit:
            state = "CRITICAL"
            self.outval = 2
        elif self._warn is not None and percused > self._warn:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0

        perfused = "| PercentMemoryUsed=%d;%s;%s;0;100 MemoryUsed=%d;;;0;%d" % (
            percused,
            intstr(self._warn),
            intstr(self._crit),
            free,
            total
            )
        self.outmsg = "%s - Physical Memory: Total: %.2fGB - " \
            "Used: %.2fGB (%.1f%%) - Free %.2fGB (%.2f%%) %s" % (
            state, total, used, percused, free, percfree, perfused)

    def swap(self):
        state = "UNKNOWN"

        TotalSwapSpaceSize = self._data.get('TotalSwapSpaceSize')
        if TotalSwapSpaceSize is None or TotalSwapSpaceSize == 0.0:
            self.outval = 0
            self.outmsg = 'OK - No Page File configured | Swap Memory Used=0;0;0;0;100'
            return

        total = float(TotalSwapSpaceSize) / 1024
        free = float(self._data.get('FreeSpaceInPagingFiles', 0.0)) / 1024
        used = total - free
        percused = used * 100.0 / total
        percfree = free * 100.0 / total

        if self._crit is not None and percused > self._crit:
            state = "CRITICAL"
            self.outval = 2
        elif self._warn is not None and percused > self._warn:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0

        perfused = "| Total_PercentageUsed=%d;%s;%s;0;100" % (
            percused,
            intstr(self._warn),
            intstr(self._crit))

        for pf in self._data['classes']['Win32_PageFileUsage']:
            name = pf['Caption'].replace(':', '_').replace('\\', '').replace('.', '_')
            perfused += " %s_AllocatedBaseSize=%d;;;;" % (name, int(pf['AllocatedBaseSize']))
            perfused += " %s_CurrentUsage=%d;;;;" % (name, int(pf['CurrentUsage']))
            perfused += " %s_PercentageUsage=%d;;;;" % (name, int((int(pf['CurrentUsage'])*100/int(pf['AllocatedBaseSize'])) if pf['AllocatedBaseSize'] != 0 else 0))
            perfused += " %s_PeakUsage=%d;;;;" % (name, int(pf['PeakUsage']))
        self.outmsg = "%s - Swap Memory: Total: %.2fGB - " \
            "Used: %.2fGB (%.1f%%) - Free %.2fGB (%.2f%%) %s" % (
            state, total, used, percused, free, percfree, perfused)

    def log(self):
        logname = self._submod
        excl = self._excl
        state = "UNKNOWN"
        messages = ""
        eventtype_names = [
            "None",
            "Error",
            "Warning",
            "AuditSuccess",
            "AuditFailure"
        ]
        event_count = [
            0, # None
            0, # Error
            0, # Warning
            0, # Information
            0, # Audit Success
            0, # Audit Failure
        ]

        if logname not in self._data['Events'] or self._data['Events'][logname] is None:
            raise Exception('UNKNOWN - Event log %s not configured.' % logname)

        events = self._data['Events'][logname]

        if isinstance(events, dict):
            if len(events) == 0:
                events = []
            else:
                events = [ events ]
        elif isinstance(events, list):
            pass
        else:
            raise Exception('UNKNOWN - Invalid log data(%s): %s' % (logname, data['Events'][logname]))

        addl = "\n"
        val=0
        for event in events:
            skip=False
            for eid, msg in self._logfilters:
                if event['EventCode'] == eid:
                    if re.search(msg, event['Message']) is not None:
                        skip=True
                        break
            if skip: continue
            event_count[int(event['EventType'])] += 1
            val += 1
            if len(addl) > 4096: continue
            addl += "%s - EventId:%s Source:\"%s\" Message:\"%s\"\n" % \
                    (event.get('Type', 'Unknown'),
                        event.get('EventCode', 'Unknown'),
                        event.get('SourceName', 'Unknown'),
                        event.get('Message', '')[:80])

        if ('Truncated' in self._data['Events'] and \
                logname in self._data['Events']['Truncated']) or \
                (self._crit is not None and val > self._crit):
            state = "CRITICAL"
            self.outval = 2
        elif self._warn is not None and val > self._warn:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0

        perfused = " |"
        for i in range(1, len(eventtype_names)):
            perfused += " %s=%d;;;;" % (eventtype_names[i], event_count[i])

        self.outmsg = "%s - Error or Warning Events=%d %s %s" %  \
            (state, val, perfused, addl)

    def uptime(self):
        state = "UNKNOWN"

        
        val = float(self._data['UpTime'])

        if self._crit is not None and val > self._crit:
            state = "CRITICAL"
            self.outval = 2
        elif self._warn is not None and val > self._warn:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0

        perfused = "| uptime=%.0f;%s;%s;;" % \
            (val, intstr(self._warn), intstr(self._crit))
        self.outmsg = "%s - Uptime of server is %.0f Hours %s\n%s" % \
            (state, val, perfused, ' '.join(sys.argv))

    def services(self):
        state = 'UNKNOWN'
        r = 0
        s = 0
        stopped_services = '\nStopped Services:\n'
        for service in self._data['Services']:
            displayname = service.get('DisplayName').lower()
            name = service.get('ServiceName').lower()
            if self._excl is not None and self._excl != '' and \
                    (re.search(self._excl, displayname) is not None or \
                        re.search(self._excl, name) is not None):
                continue
            if re.search(self._incl, displayname) is not None or \
                re.search(self._incl, name) is not None:
                status = service.get('Status')
                state = service.get('State', 'Stopped')
                if (isinstance(status, int) and status == 4) or state == 'Running':
                    r += 1
                else:
                    s += 1
                    stopped_services += " * %s(%s)\n" % \
                        (service.get('DisplayName', 'Unknown'), name)

        if self._crit is not None and s >= self._crit:
            state = "CRITICAL"
            self.outval = 2
        elif self._warn is not None and s >= self._warn:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0

        perfused = " | Stopped=%d;%s;%s;; Running=%d;;;;" % \
            (s, intstr(self._warn),
                intstr(self._crit), r)
        self.outmsg = "%s - %d Services Stopped - %d Services Running %s\n%s" % \
            (state, s, r, perfused, stopped_services if self.outval > 0 else '')

    def hddrives(self):
        state = 'UNKNOWN'

        disk_messages = []
        disk_addl = []
        disk_perfs = []
        status_crit = 0
        status_warn = 0

        def check_disk(disk):
            totalg = float(disk['Size']) / 1024.0 / 1024.0 / 1024.0
            freeg = float(disk['FreeSpace']) / 1024.0 / 1024.0 / 1024.0
            usedg = totalg - freeg
            percused =  usedg / totalg * 100.0
            disk_messages.append(" %s=%.1f%%Used" % (disk.get('Name'), percused))
            addl = "Disk %s Total: %.2fG - Used: %.2fG (%.1f%%)" % (
                disk['Name'],
                totalg,
                usedg,
                percused)
            disk_addl.append(addl)
            perf = "%s=%.1f;%s;%s;0;100 " % (
                disk['Name'].replace(':', '').lower(),
                percused,
                intstr(self._warn),
                intstr(self._crit))
            disk_perfs.append(perf)
            if self._crit is not None and percused >= self._crit:
                disk_addl[-1] += "***"
                return 2
            elif self._warn is not None and percused >= self._warn:
                disk_addl[-1] += "***"
                return 1
            return 0

        disklist = self._data.get('Disks', [])
        if isinstance(disklist, dict):
            disklist = [ disklist ]
        elif isinstance(disklist, list):
            pass
        else:
            disklist = []

        for disk in disklist:
            if int(disk['DriveType']) != 3:
                continue
            s = check_disk(disk)
            if s == 2:
                status_crit += 1
            elif s == 1:
                status_warn += 1

        if status_crit > 0:
            state = "CRITICAL"
            self.outval = 2
        elif status_warn > 0:
            state = "WARNING"
            self.outval = 1
        else:
            state = "OK"
            self.outval = 0

        self.outmsg = "%s - %s | %s\n%s" % \
            (state, ",".join(disk_messages), " ".join(disk_perfs), "\n".join(disk_addl))

