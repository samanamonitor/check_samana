#!/usr/bin/python3

from samana.nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
from samana.base import auth_file
import smbc
import fnmatch
import sys, getopt
import traceback

Byte = lambda x: int(x)
Kilo = lambda x: x*1024
Mega = lambda x: Kilo(x)*1024
Giga = lambda x: Mega(x)*1024
addl_str = lambda x:"%s: %s\n" % (x[0],x[1])

def usage():
  return """Check SMB File Size v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2021 Samana Group LLC

Usage:
  %s -H <host name> -P <path> ( -U <username> -p <password> | -a <auth file>) [ -w <warning size in bytes> ] [ -c <critical size in bytes> ] [ -f <filter string> ]

  <host name>        Windows Server to be queried
  <path>             Path inside server to search for file sizes. Includes share name and any directories.
  <username>         User in Windows Domain (domain\\user) or local Windows user
  <password>         User password
  <auth file>        File containing credentials. In the file, username cannot be UPN.
  <warning size>     Size in bytes of files. Can use K, M or G for kilobyte, megabyte and gigabyte. Ex 10M
  <critical size>    Size in bytes of files. Can use K, M or G for kilobyte, megabyte and gigabyte. Ex 10M
  <filter string>    String that will filter files. String expects wildcards like * or ?. Ex. *.vhd
""" % sys.argv[0] if len(sys.argv) > 0 else "???????"

def getbytes(val):
    if val is None or val == '':
        return None
    try:
        if val[-1] in ( 'k', 'K' ):
            return  Kilo(Byte(val[:-1]))
        elif val[-1] in ( 'm', 'M' ):
            return Mega(Byte(val[:-1]))
        elif val[-1] in ( 'g', 'G'):
            return Giga(Byte(val[:-1]))
        else:
            return Byte(val)
    except:
        raise CheckUnknown("Invalid value %s" % val)


def getfiles(context, uri, warnsize=None, critsize=None, filters=None):
    size = 0
    filedata = { "size": 0, "warning": [], "critical": []}
    dirs = context.opendir(uri)
    dents = dirs.getdents()
    for d in dents:
        if d.name in (".", ".."):
            continue

        path = "%s/%s" % (uri, d.name)
        if d.smbc_type == 7:
            fd = getfiles(context, path, warnsize, critsize, filters)
            filedata['size'] += fd['size']
            filedata['warning'] += fd['warning']
            filedata['critical'] += fd['critical']
            continue
        if filters is not None and len(fnmatch.filter([d.name], filters)) == 0:
            continue

        s = context.stat(path)
        if critsize is not None and s[6] > critsize:
            filedata['critical']+= [(path, s[6])]
        elif warnsize is not None and s[6] > warnsize:
            filedata['warning'] += [(path, s[6])]
        filedata['size'] += s[6]
    return filedata


def main(argv):
    hostaddress = None
    warning = None
    critical = None
    username = None
    password = None
    domain = None
    filters = None
    path = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hH:P:U:p:a:w:c:f:")
        for o, a in opts:
            if o == '-H':
                hostaddress = a
            elif o == '-P':
                path = a
            elif o == '-w':
                warning = getbytes(a)
            elif o == '-c':
                critical = getbytes(a)
            elif o == '-U':
                username = a
            elif o == '-p':
                password = a
            elif o == '-a':
                (username, password, domain) = auth_file(a)
                if domain is not None:
                    username = "%s\\%s" % (domain, username)
            elif o == '-f':
                filters = a
            elif o == '-h':
                raise CheckUnknown("Help", addl=usage())
            else:
                raise CheckUnknown("Unknown Argument", addl=usage())

        if hostaddress is None:
            raise CheckUnknown("Host Address not defined")
        if username is None:
            raise CheckUnknown("Auth data not defined")
        if path is None:
            raise CheckUnknown("Path for files needed")

        def auth(srv, shr, wkg, u, p):
            return (domain, username, password)

        context = smbc.Context(auth_fn=auth)

        filedata = getfiles(context, "smb://%s/%s" % (hostaddress, path), 
            warning, critical, filters)

        critical_files = len(filedata['critical'])
        warning_files = len(filedata['warning'])
        addl = ""
        for l in map(addl_str,filedata['critical']):
            addl += l
        for l in map(addl_str, filedata['warning']):
            addl += l
        if critical_files > 0:
            raise CheckCritical("%d Files larger than %s found" % 
                (critical_files, critical), addl=addl)
        elif warning_files > 0:
            raise CheckWarning("%d Files larger than %s found" % 
                (warning_files, warning), addl=addl)

        out = CheckResult("Files Checked")

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
