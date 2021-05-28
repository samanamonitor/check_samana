#!/usr/bin/python

import sys, getopt
import json
import re
import samanaetcd as etcd
import time

from os import environ

debug = 0

def help():
    print "%s\n%s -H <hostid> -m <module> [-s <submodule>] [-c <critical>] [-w <warning>]" % (sys.argv, sys.argv[0])
    sys.exit(3)

def cpu(data, crit, warn):
    global debug
    state = "UNKNOWN"
    graphmax = 100

    critval = 101
    warnval = 101
    if debug:
        print data
    
    if crit is not None:
        critval = float(crit)
    if warn is not None:
        warnval = float(warn)
    val = 100.0 - float(data['PercentIdleTime'])

    if val > critval:
        state = "CRITICAL"
        outval = 2
    elif val > warnval:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0
    
    perfusage = "cpuLoad=%.0f;%s;%s;0;%d" % (
        val, 
        warn if warn is not None else '', 
        crit if crit is not None else '', 
        graphmax)
    # TODO: need to create script to migrate old data to include these values on old systems
    perfpriv = "" #"priv=%.0f;;;" % data['PercentPrivilegedTime']
    perfuser = "" #"user=%.0f;;;" % data['PercentUserTime']
    perfirq  = "" #"interrupt=%.0f;;;" % data['PercentInterruptTime']
    outmsg = "%s - CPU Usage %0.f %%| %s %s %s %s" % (
        state, val, perfusage, perfpriv, perfuser, perfirq)
    return (outval, outmsg)

def ram(data, crit, warn):
    state = "UNKNOWN"
    
    total = float(data['TotalVisibleMemorySize']) / 1024.0
    free = float(data['FreePhysicalMemory']) / 1024.0
    used = total - free
    percused = used * 100.0 / total
    percfree = free * 100.0 / total

    critval = 101
    warnval = 101
    if crit is not None:
        critval = float(crit)
    if warn is not None:
        warnval = float(warn)

    if percused > critval:
        state = "CRITICAL"
        outval = 2
    elif percused > warnval:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    perfused = "'Physical Memory Used'=%d;;;0;%d 'Physical Memory Utilization'=%d;%s;%s;0;100" % (
        free,
        total,
        percused,
        warn if warn is not None else '',
        crit if crit is not None else '')
    outmsg = "%s - Physical Memory: Total: %.2fGB - Used: %.2fGB (%.1f%%) - Free %.2fGB (%.2f%%) | %s" % (
        state, total, used, percused, free, percfree, perfused)

    return (outval, outmsg)

def swap(data, crit, warn):
    state = "UNKNOWN"

    TotalSwapSpaceSize = data.get('TotalSwapSpaceSize')
    if TotalSwapSpaceSize is None or TotalSwapSpaceSize == 0.0:
        return (0, 'OK - No Page File configured | Swap Memory Used=0;0;0;0;100')

    total = float(TotalSwapSpaceSize) / 1024 / 1024
    free = float(data.get('FreeSpaceInPagingFiles', 0.0)) / 1024 / 1024
    used = total - free
    percused = used * 100.0 / total
    percfree = free * 100.0 / total

    critval = 101
    warnval = 101
    if crit is not None:
        critval = float(crit)
    if warn is not None:
        warnval = float(warn)

    if percused > critval:
        state = "CRITICAL"
        outval = 2
    elif percused > warnval:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    perfused = "Swap Memory Used=%d;%s;%s;0;100" % (
        percused,
        warn if warn is not None else '',
        crit if crit is not None else '')
    outmsg = "%s - Swap Memory: Total: %.2fGB - Used: %.2fGB (%.1f%%) - Free %.2fGB (%.2f%%) | %s" % (
        state, total, used, percused, free, percfree, perfused)

    return (outval, outmsg)

def log(data, logname, crit, warn):
    state = "UNKNOWN"
    messages = ""

    if logname not in data['Events']:
        return (3, "UNKNOWN - Invalid event log.")

    critval = 101
    warnval = 101
    if crit is not None:
        critval = int(crit)
    if warn is not None:
        warnval = int(warn)

    if logname not in data['Events'] or data['Events'][logname] is None:
        return (3, 'UNKNOWN - Event log %s not configured.' % logname)

    events = data['Events'][logname]

    if isinstance(events, dict):
        if len(events) == 0:
            events = []
        else:
            events = [ events ]
    elif isinstance(events, list):
        pass
    else:
        return (3, 'UNKNOWN - Invalid log data(%s): %s' % (logname, data['Events'][logname]))

    val = len(events)

    if 'Truncated' in data['Events'] and logname in data['Events']['Truncated'] or val > critval:
        state = "CRITICAL"
        outval = 2
    elif val > warnval:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    if outval > 0:
        messages = "\n"
        for i in events:
            if 'Message' in i:
                messages += i['Message'] + "\n"
            else:
                messages += "<UNKNOWN>\n"

    outmsg = "%s - Error or Warning Events=%d %s" %  \
        (state, val, messages)
    return (outval, outmsg)

def services(data, crit, warn, incl, excl):
    state = 'UNKNOWN'
    if incl == '':
        return (3, 'UNKNOWN - No services defined to be monitored')

    r = 0
    s = 0
    stopped_services = '\nStopped Services:\n'
    for service in data['Services']:
        displayname = service['DisplayName'].lower()
        name = service['ServiceName'].lower()
        if excl is not None and excl != '' and \
                (re.search(excl, displayname) is not None or \
                    re.search(excl, name) is not None):
            continue
        if re.search(incl, displayname) is not None or re.search(incl, name) is not None:
            if (isinstance(service['Status'], int) and int(service['Status']) == 4) or \
                    (isinstance(service['State'], unicode) and service['State'] == u'Running'):
                r += 1
            else:
                s += 1
                stopped_services += " * %s(%s)\n" % (service['DisplayName'], name)

    critval = 101
    warnval = 101
    if debug:
        print data
    
    if crit is not None:
        critval = int(crit)
    if warn is not None:
        warnval = int(warn)


    if s >= critval:
        state = "CRITICAL"
        outval = 2
    elif s >= warnval:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    outmsg = "%s - %d Services Running - %d Services Stopped %s" % (
        state, r, s, stopped_services if outval > 0 else '')
    return (outval, outmsg)

def hddrives(data, crit, warn, srch):
    state = 'UNKNOWN'

    critval = 101
    warnval = 101
    if crit is not None:
        critval = float(crit)
    if warn is not None:
        warnval = float(warn)

    disk_messages = []
    disk_perfs = []
    status_crit = 0
    status_warn = 0

    def check_disk(disk):
        totalg = float(disk['Size']) / 1024.0 / 1024.0 / 1024.0
        freeg = float(disk['FreeSpace']) / 1024.0 / 1024.0 / 1024.0
        usedg = totalg - freeg
        percused =  usedg / totalg * 100.0
        message = "Disk %s Total: %.2fG - Used: %.2fG (%.1f%%)" % (
            disk['Name'],
            totalg,
            usedg,
            percused)
        disk_messages.append(message)
        perf = "%s=%.1f;%s;%s;0;100 " % (
            disk['Name'],
            percused,
            warn if warn is not None else '',
            crit if crit is not None else '')
        disk_perfs.append(perf)
        if percused >= critval:
            return 2
        elif percused >= warnval:
            return 1
        return 0

    if isinstance(data['Disks'], list):
        for disk in data['Disks']:
            if disk['DriveType'] != 3:
                continue
            s = check_disk(disk)
            if s == 2: 
                status_crit += 1
            elif s == 1: 
                status_warn += 1
    else:
        s = check_disk(data['Disks'])
        if s == 2: 
            status_crit += 1
        elif s == 1: 
            status_warn += 1

    if status_crit > 0:
        state = "CRITICAL"
        outval = 2
    elif status_warn > 0:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    outmsg = "%s - %s | %s" % (state, " ".join(disk_messages), " ".join(disk_perfs))
    return (outval, outmsg)

def uptime(data, crit, warn):
    state = "UNKNOWN"

    if debug:
        print data
    
    val = data['UpTime']

    try:
        crit = float(crit)
        if val > crit:
            return (2, "CRITICAL - Uptime of server is %.0f Hours | uptime=%.0f;%s;%s;" % (val, val, str(warn), str(crit)))
    except:
        pass

    try:
        warn = float(warn)
        if val > warn:
            return (1, "WARNING - Uptime of server is %.0f Hours | uptime=%.0f;%s;%s;" % (val, val, str(warn), str(crit)))
    except:
        pass

    return (0, "OK - Uptime of server is %.0f Hours | uptime=%.0f;%s;%s;" % (val, val, str(warn), str(crit)))

def main(argv):
    hostid = ''
    port = 11000
    module = ''
    submod = ''
    warn = None
    crit = None
    search = ""
    incl = ''
    excl = ''
    test = None
    url = None
    etcdserver = ''
    etcdport = '2379'

    global debug

    try:
        opts, args = getopt.getopt(argv, "H:m:c:w:p:s:r:i:e:l:x:dt:U:E:")
    except getopt.GetoptError:
        help()
    
    for opt, arg in opts:
        if opt == '-h':
            help()
        elif opt == "-H":
            hostid = arg
        elif opt == "-p":
            port = arg
        elif opt == "-m":
            module = arg
        elif opt == "-c":
            crit = arg
        elif opt == "-w":
            warn = arg
        elif opt == "-s":
            submod = arg
        elif opt == "-r":
            search = arg
        elif opt == "-i":
            incl = arg
        elif opt == "-e":
            excl = arg
        elif opt == "-d":
            debug = 1
        elif opt == "-t":
            test = arg
        elif opt == "-U":
            url = arg
        elif opt == "-E":
            temp = arg.split(':')
            etcdserver = temp[0]
            if len(temp) > 1:
                etcdport = temp[1]
        else:
            help()

    if module == "":
        help()

    if test is not None:
        try:
            with open(test, "r") as f:
                data = json.load(f)
        except:
            print "UNKNOWN - Unable to load data from file %s" % test
            exit(3)
    else:
        if hostid == "": 
            print "UNKNOWN - Host ID not specified."
            exit(3)

        if url is not None:
            url_re = re.search(r'([^:]+)://([^:/]+)(:([^/]+))', url)
            if url_re is None:
                print "UNKNOWN - Unable to extract etcd server data from %s" % url
                exit(3)
            protocol=url_re.group(1)
            host=url_re.group(2)
            port=url_re.group(4)
            if port is None:
                port=2379
            c = etcd.Client(host=host, port=port, protocol=protocol)
        else:
            if etcdserver != '':
                c = etcd.Client(host=etcdserver, port=etcdport)
            else:
                c = etcd.Client(port=2379)

        try:
            data =json.loads(c.get("/samanamonitor/data/%s" % hostid).value)
            age_secs = time.time() - data['epoch']
            if age_secs > 600:
                print "UNKNOWN - Data is too old %d seconds" % age_secs
                exit(3)
        except etcd.EtcdKeyNotFound:
            print "UNKNOWN - ServerID \"%s\" not found in the database" % hostid
            exit(3)
        except ValueError:
            print "UNKNOWN - Data for ServerID \"%s\" is corrupt" % hostid
            exit(3)
        except etcd.EtcdException as e:
            print "UNKNOWN - Server not responding. %s" % str(e)
            exit(3)

    outmsg = "UNKNOWN - Data is unavailable"
    outval = 3 
    
    if module == 'cpu':
        (outval, outmsg) = cpu(data, crit, warn)
    elif module == 'ram':
        (outval, outmsg) = ram(data, crit, warn)
    elif module == 'swap':
        (outval, outmsg) = swap(data, crit, warn)
    elif module == 'log':
        (outval, outmsg) = log(data, submod, crit, warn)
    elif module == 'services':
        (outval, outmsg) = services(data, crit, warn, incl, excl)
    elif module == 'hddrives':
        (outval, outmsg) = hddrives(data, crit, warn, search)
    elif module == 'uptime':
        (outval, outmsg) = uptime(data, crit, warn)
        
    print outmsg
    exit(outval)

if __name__ == "__main__":
    main(sys.argv[1:])
