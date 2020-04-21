#!/usr/bin/python

import urllib
import sys, getopt
import json
import socket
import re
import etcd

from os import environ

debug = 0

def help():
    print "check_samana2.py -H <hostid> -m <module> [-s <submodule>] [-c <critical>] [-w <warning>]"
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
    
    perfusage = "cpu=%.0f;%s;%s;0;%d" % (
        val, 
        warn if warn is not None else '', 
        crit if crit is not None else '', 
        graphmax)
    perfpriv = "priv=%.0f;;;" % data['PercentPrivilegedTime']
    perfuser = "user=%.0f;;;" % data['PercentUserTime']
    perfirq  = "interrupt=%.0f;;;" % data['PercentInterruptTime']
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

    perfused = "Physical Memory Used'=%dG%s;%s;0;100" % (
        percused,
        warn if warn is not None else '',
        crit if crit is not None else '')
    outmsg = "%s - Physical Memory: Total: %.2fGB - Used: %.2fGB (%.1f%%) - Free %.2fGB (%.2f%%) | %s" % (
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

    val = len(data['Events'][logname])
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
        for i in data['Events'][logname]:
            messages += i['Message'] + "\n"

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
            if int(service['Status']) == 4:
                r += 1
            else:
                s += 1
                stopped_services += displayname

    critval = 101
    warnval = 101
    if debug:
        print data
    
    if crit is not None:
        critval = int(crit)
    if warn is not None:
        warnval = int(warn)


    if s > critval:
        state = "CRITICAL"
        outval = 2
    elif s > warnval:
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    outmsg = "%s - %d Services Running - %d Services Stopped %s" % (
        state, r, s, stopped_services)
    return (outval, outmsg)

def hddrives(s, d, crit, warn, srch):
    state = 'UNKNOWN'
    if srch == '':
        return (3, "UNKNOWN - Could not find a drive matching '' or the WMI data returned is invalid. Available Drives are C:, D:")

    data = json.loads(d)['data']
    search = srch.upper()
    total = 0
    used = 0
    free = 0
    percused = 0
    percfree = 0
    usedbytes = 0
    critval = ''
    warnval = ''
    if crit != -1:
        critval = crit
    if warn != -1:
        warnval = warn

#  C: Total=59.995GB, Used=32.598GB (54.3%), Free=27.397GB (45.7%)     |'C: Space'=35002163200B; 'C: Utilisation'=54.3%;95;98;
    for x in data:
        if x['name'].upper().find(search) != -1:
            total = float(x['totalsize']) / 1024
            used = float(x['used']) / 1024
            free = float(x['free']) / 1024
            percused = float(x['used']) * 100 / float(x['totalsize'])
            percfree = float(x['free']) * 100 / float(x['totalsize'])
            usedbytes = int(x['used']) * 1024 * 1024
            break

    if usedbytes == 0:
        return (3, "UNKNOWN - no data found for the drive {0}".format(srch))

    if crit != -1 and percused >= float(crit):
        state = "CRITICAL"
        outval = 2
    elif warn != -1 and percused >= float(warn):
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0

    outmsg = "%s - %s Total=%.2fGB, Used=%.2fGB (%.1f%%), Free=%.2fGB (%.1f%%) | '%s Space'=%dB '%s Utilization'=%.1f%%;%s;%s;0;100" % (
        state, search, total, used, percused, free, percfree, search, usedbytes, search, percused, warnval, critval) 
    return (outval, outmsg)

def uptime(d, crit, warn):
    state = "UNKNOWN"

    data = json.loads(d)
    if crit != -1 and int(data) > int(crit):
        state = "CRITICAL"
        outval = 2
    elif warn != -1 and int(data) > int(warn):
        state = "WARNING"
        outval = 1
    else:
        state = "OK"
        outval = 0
    
    temp = int(data / 1000)
    seconds = temp % 60
    temp = (temp - seconds) / 60
    minutes = temp % 60
    temp = (temp - minutes) / 60
    hours = temp % 24
    temp = (temp - hours) / 24
    days = temp
    
    outmsg = "%s - Uptime of server is %dms - %d Days, %d Hours, %d Minutes, %d Seconds | uptime=%d;%d;%d;;" % \
        (state, data, days, hours, minutes, seconds, data, int(warn), int(crit))
    return (outval, outmsg)

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
    global debug

    try:
        opts, args = getopt.getopt(argv, "H:m:c:w:p:s:r:i:e:l:x:d")
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

    if hostid == "" or module == "":
        help()

    c = etcd.Client(port=2379)

    try:
        data =json.loads(c.get("/samanamonitor/data/%s" % hostid).value)
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
    elif module == 'log':
        (outval, outmsg) = log(data, submod, crit, warn)
    elif module == 'services':
        (outval, outmsg) = services(data, crit, warn, incl, excl)
    elif module == 'hddrives':
        (outval, outmsg) = hddrives(submod, data, crit, warn, search)
    elif module == 'uptime':
        (outval, outmsg) = uptime(data, crit, warn)
        
    print outmsg
    exit(outval)

if __name__ == "__main__":
    main(sys.argv[1:])
