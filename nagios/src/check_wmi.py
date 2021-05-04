#!/usr/bin/python3

import json
import samanaetcd as etcd
import csv
import sys, getopt
import traceback
import subprocess

wmi_exec="/usr/local/bin/wmic"
timeout=60

class CheckNagiosException(Exception):
    def __init__(self, info=None, perf_data=None, addl=None):
        self.info = info if info is not None else "Unknown Exception"
        self.perf_data = perf_data if perf_data is not None else ""
        self.addl = addl if addl is not None else ""

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
  %s -H <host name> -a <auth file> > -e <etcd server> -t <ttl>

  <host name>        Windows Server to be queried
  <auth file>        file name containing user's credentials
  <etcd server>      Etcd server IP/Hostname and port(optional). Default port value is 2379. Format: x.x.x.x[:2379]
  <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
""" % argv[0] if len(argv) > 0 else "???????"


def query_wmi(host, authfile, query="", wmi_class="", wmi_properties=[], wmi_filter=[]):
    if wmi_class == "" and query == "":
        raise CheckNagiosUnknown("No WMI Query defined")

    if wmi_class != "":        
        query = "SELECT %s FROM %s%s%s" % (','.join(wmi_properties), \
            wmi_class, " WHERE " if len(wmi_filter) > 0 else "", " and ".join(wmi_filter))
    cmd=[wmi_exec, "-A", authfile, "//%s" % host, query ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE, encoding="ascii")
    output, err = p.communicate(timeout=timeout)
    if p.return_code != 0
        raise CheckNagiosUnknown(info="Error executing wmic", addl="STDOUT=%s\nSTDERR=%s" % (output, err))
    return output.split('\n')


def main(argv):
    try:
        etcdserver = '127.0.0.1'
        etcdport = '2379'
        opts, args = getopt.getopt(sys.argv[1:], "H:ha:e:t:")
        ttl = 300
        hostaddress = None
        authfile = None

        for o, a in opts:
            if o == '-H':
                hostaddress = a
            elif o == '-a':
                authfile = a
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
        if authfile is None:
            raise CheckNagiosUnknown("Auth file not defined")

        a = query_wmi(hostaddress, authfile, wmi_class="win32_logicaldisk", wmi_properties=["*"])

        print("OK - %s | %s\n%s"("", "", ""))
    except CheckNagiosWarning as e:
        print("WARNING - %s | %s\n%s" % (e.info, e.perf_data, e.addl))
        exit(1)
    except CheckNagiosError as e:
        print("ERROR - %s | %s\n%s" % (e.info, e.perf_data, e.addl))
        exit(2)
    except CheckNagiosUnknown as e:
        print("UNKNOWN - %s | %s\n%s" % (e.info, e.perf_data, e.addl))
        exit(3)
    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        print("UNKNOWN - Error: %s at line %s\n%s" % (str(e), tb.tb_lineno, traceback_info))
        exit(3)

if __name__ == "__main__":
  main()
