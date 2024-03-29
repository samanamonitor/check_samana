#!/usr/bin/python3

import json
import pywmi
import time
from samana.nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
from samana.base import get_dns_ip, ping_host, perf, auth_file
from samana import etcd
from hashlib import md5, sha256
import traceback
import sys
from cgi import parse_qs, escape


data = {
    "auth": {
        "username": "",
        "password": "",
        "domain": ""
    },
    "debug": 0,
    "hostname": "",
    "etcdserver": { "address": "127.0.0.1", "port": "2379", "secure": False },
    "warning": [],
    "critical": [],
    "warning-str": "",
    "critical-str": "",
    "ttl": 300,
    "id-type": "fqdn",
    "queries": []
}
STATUS = [ 'OK', 'WARNING', 'CRITICAL', 'UNKNOWN' ]
perfnames = [ 'dns', 'loss', 'ping', 'wmitime', 'etcdtime', 'process_data' ]

def usage(msg):
  return """%sCheck WMI v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2021 Samana Group LLC

Usage:
  %s -H <host name> ( -U <username> -p <password> | -a <auth file>) [-i <id type>] [-n <namespace>] [-e <etcd server>] [-m <memcache server>] [-t <ttl>] [ -w dnswarn,pingwarn,packetlosswarn,wmiwarn ] [ -c dnscrit,pingcrit,packetlosscrit,wmicrit ]

  <host name>        Windows Server to be queried
  <username>         User in Windows Domain (domain\\user) or local Windows user
  <password>         User password
  <auth file>        File containing credentials. In the file, username cannot be UPN.
  <id type>          Id encoding, can be one of "md5", "sha256" or "fqdn". Default is "md5"
  <namespace>        WMI namespace, default root\\cimv2
  <etcd server>      Etcd server IP/Hostname and port(optional). Default value 127.0.0.1:2379
  <memcache server>  Memcached server IP/Hostname and port(optional). Format <server ip/hostname>:11211. If set, etcd will not be used.
  <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
""" % ("%s\n" % msg if msg is not None else "", sys.argv[0] if len(sys.argv) > 0 else "???????")

def string_to_threshold(name, s):
    ret = {
        "name": name,
        "enabled": False,
        "start": { "value": 0, "infinity": False},
        "end": { "value": 0, "infinity": True},
        "invert": False,
        "error": False,
        "str": s
    }
    if s == "":
        return ret
    r = s.split('@')
    if len(r) > 1:
        ret['invert'] = True
        t = r[1]
    else:
        t = r[0]
    vals = t.split(':')
    if len(vals) > 2:
        ret["error"] = True
        return ret
    if len(vals) == 1:
        if not vals[0].isnumeric():
            ret["error"] = True
            return ret
        ret['start']['infinity'] = False
        ret['start']['value'] = 0
        ret['end']['infinity'] = False
        ret['end']['value'] = vals[0]
        ret['enabled'] = True
    elif len(vals) == 2:
        if vals[0] == "~":
            ret['start']['infinity'] = True
        else:
            if not vals[0].isnumeric():
                ret["error"] = True
                return ret
            ret['start']['value'] = int(vals[0])
        if vals[1] == "":
            ret['end']['infinity'] = True
        else:
            if not vals[1].isnumeric():
                ret["error"] = True
                return ret
            ret['end']['infinity'] = False
            ret['end']['value'] = int(vals[1])
        ret['enabled'] = True
    return ret

def process_thresholds(threshold):
    ret=[]
    tlist = threshold.split(",")

    for i in range(len(perfnames)):
        try:
            ret += [string_to_threshold(perfnames[i], tlist[i])]
        except IndexError:
            ret += [string_to_threshold(perfnames[i], '')]
    return ret

def validate_input(data):
    data['warning'] = process_thresholds(data.get("warning-str", ""))
    data['critical'] = process_thresholds(data.get("critical-str", ""))

    if 'ttl' not in data:
        data['ttl'] = 300
    if 'debug' not in data:
        data['debug'] = 0
    if data["auth"]["username"] == "":
        raise CheckUnknown("Missing Username")
    if data["auth"]["password"] == "":
        raise CheckUnknown("Missing Password")
    if data["hostname"] == "":
        raise CheckUnknown("Missing Hostname")
    if not data["etcdserver"]["port"].isnumeric():
        raise CheckUnknown("Invalid Etcd Server port")
    if not isinstance(data["queries"], list) and len(data["queries"]) == 0:
        raise CheckUnknown("Missing Queries")
    for i in range(len(data["queries"])):
        if "name" not in data["queries"][i] or \
            "namespace" not in data["queries"][i] or \
            "query" not in data["queries"][i]:
            raise CheckUnknown("Invalid query %s" % data["queries"])
    if len(data["warning"]) != len(perfnames):
        raise CheckUnknown("Invalid warning data %s" % json.dumps(data["warning"]))
    for i in range(len(perfnames)):
        if data["warning"][i]["error"]:
            raise CheckUnknown("Invalid warning data at %s with string %s" % 
                    (data["warning"][i]["name"], data["warning"][i]["str"]))

def get_id(data, idtype='md5'):
    computer = data['computer'][0]['properties']
    fqdn = "%s.%s" % (computer['DNSHostName'], computer['Domain'])
    fqdn = fqdn.lower()
    if idtype == 'md5':
        return md5(fqdn.encode("utf8")).hexdigest().upper()
    elif idtype == 'sha256':
        return sha256(fqdn.encode("utf8")).hexdigest().upper()
    elif idtype == 'fqdn':
        return fqdn
    return "invalid"

def process_data(data):
    try:

        process_start = time.time()
        perfvalues = [0] * len(perfnames)
        (hostip, perfvalues[0]) = get_dns_ip(data["hostname"])
        ping_data = ping_host(hostip, count=1)
        perfvalues[1] = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])
        perfvalues[2] = ping_data['avg']

        wmi_start = time.time()
        qs={ "root\\cimv2": [{ "name": "computer", "namespace": "root\\cimv2", "query": "SELECT * FROM Win32_ComputerSystem", "class": ""}]}
        wmi_out={}
        for i in range(len(data["queries"])):
            ns=data["queries"][i]["namespace"]
            if ns not in qs:
                qs[ns] = []
            qs[ns] += [data["queries"][i]]
        for ns in qs.keys():
            pywmi.open(data["hostname"], data["auth"]["username"], data["auth"]["password"], data["auth"]["domain"], ns)
            for q in range(len(qs[ns])):
                wmi_out[qs[ns][q]['name']] = pywmi.query(qs[ns][q]['query'])
            pywmi.close()
        perfvalues[3] = int((time.time() - wmi_start) * 1000)

        data['ID'] = get_id(wmi_out, data['id-type'])
        etcd_start = time.time()
        c = etcd.Client(host=data['etcdserver']['address'], port=data['etcdserver']['port'])
        c.put("samanamonitor2/data/%s" % data['ID'], json.dumps(wmi_out), data['ttl'])
        perfvalues[4] = int((time.time() - etcd_start) * 1000)
        perfvalues[5] = int((time.time() - process_start) * 1000)
        perf_data = []
        for i in range(len(perfnames)):
            w = data['warning'][i]['end']['value'] if data['warning'][i]['enabled'] else None
            c = data['critical'][i]['end']['value'] if data['critical'][i]['enabled'] else None
            perf_data += [perf(perfnames[i], perfvalues[i], w, c)]
        addl = ""
        if data["debug"] == 1:
            addl += "\n" + ' '.join(sys.argv)
        out = CheckResult("Data Collected ID=%s" % data['ID'], perf_data=perf_data, addl=addl)
    except CheckUnknown as e:
        return { "status": e.status, "info1": e.info }
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

    return out

def application (environ, start_response):

    res = {}
    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError):
        request_body_size = 0
    try:
        data = json.load(environ['wsgi.input'])
        validate_input(data)
        out=process_data(data)
    except json.decoder.JSONDecodeError as e:
        out = CheckUnknown("Unable to decode input", addl=str(e)).result
    except CheckException as e:
        out = e.result

    res['status'] = out.status
    res['info1'] = out.info
    res['perf1'] = out.perf_data
    res['info2'] = out.addl
    res['perf2'] = ""

    response_body = json.dumps(res).encode('utf-8')

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

def main(argv):
    import getopt
    try:
        opts, args = getopt.getopt(sys.argv[1:], "H:U:p:q:e:t:w:c:a:i:h")
    except getopt.GetoptError as e:
        print(e)
        print(usage())

    for o, a in opts:
        if o == '-H':
            data['hostname'] = a
        elif o == '-U':
            temp = a.split("\\")
            if len(temp) > 1:
                data['auth']['domain'] = temp[0]
                data['auth']['username'] = temp[1]
            else:
                data['auth']['username'] = a
        elif o == '-p':
            data['auth']['password'] = a
        elif o == '-q':
            try:
                data['queries'] = json.loads(a)
            except Exception:
                data['queries'] = None
        elif o == '-e':
            temp = a.split(':')
            data['etcdserver']['address'] =temp[0]
            if len(temp) > 1:
                data['etcdserver']['port'] = temp[1]
        elif o == '-t':
            data['ttl'] = a
        elif o == '-w':
            data["warning-str"] = a
        elif o == '-c':
            data["critical-str"] = a
        elif o == '-a':
            (data['auth']['username'], data['auth']['password'], 
                data['auth']['domain']) = auth_file(a)
        elif o == "-i":
            data['id-type'] = a
        elif o == '-h':
            print(usage())
            return 3

    try:
        validate_input(data)
        out=process_data(data)
    except json.decoder.JSONDecodeError as e:
        out = CheckUnknown("Unable to decode input", addl=str(e)).result
    except CheckException as e:
        out = e.result

    print(out)
    return out.status

if __name__ == "__main__":
    exit(main(sys.argv))
