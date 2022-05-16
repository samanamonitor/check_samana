#!/usr/bin/python3

import json
import pywmi

data = {
    "auth": {
        "username": "",
        "password": "",
        "domain": ""
    },
    "hostname": "",
    "etcdserver": { "address": "127.0.0.1", "port": "2379", "secure": False },
    "warning": [],
    "critical": [],
    "ttl": 300,
    "id-type": 0,
    "queries": []
}
STATUS = [ 'OK', 'WARNING', 'CRITICAL', 'UNKNOWN' ]
perfnames = [ 'dns', 'loss', 'ping', 'wmitime' ]

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
            ret += string_to_threshold(perfnames[i], tlist[i])
        except IndexError:
            ret += string_to_threshold(perfnames[i], '')
    return ret

def validate_input(data):
    if data["auth"]["username"] == "":
        return { "status": 3, "info1": "Missing Username"}
    if data["auth"]["password"] == "":
        return { "status": 3, "info1": "Missing Password"}
    if data["hostname"] == "":
        return { "status": 3, "info1": "Missing Hostname"}
    if not data["etcdserver"]["port"].isnumeric():
        return { "status": 3, "info1": "Invalid Etcd Server port"}
    if len(data["queries"]) == 0:
        return { "status": 3, "info1": "Missing Queries"}
    for i in range(len(data["queries"])):
        if "name" not in data["queries"][i] or \
            "namespace" not in data["queries"][i] or \
            "query" not in data["queries"][i]:
            return {"status": 3, "info1": "Invalid query"}
    if len(data["warning"]) != len(perfnames):
        return { "status": 3, "info1": "Invalid warning data"}
    for i in range(len(perfnames)):
        if data["warning"][i]["error"]:
            return { "status": 3, 
                "info1": "Invalid warning data at %s with string %s" % 
                    (data["warning"][i]["name"], data["warning"][i]["str"])}
    return {"status": 0}

def process_data(data):
    try:
        (hostip, dns_time) = get_dns_ip(data["hostname"])
        ping_data = ping_host(hostip)
        perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])

        wmi_start = time.time()
        qs={}
        out={}
        for i in range(data["queries"]):
            ns=data["queries"][i]["namespace"]
            if ns not in qs:
                qs[ns] = []
            qs[ns] += data["queries"][i]
        for ns in qs.keys():
            pywmi.open(data["hostname"], data["username"], data["password"], data["domain"], ns)
            for q in qs[ns]:
                out[qs[ns][q]['name']] = pywmi.query(qs[ns][q]['query'])
            pywmi.close()
    except CheckUnknown as e:
        return { "status": e.status, "info1": e.info }
    except Exception as e:
        return {"status": "3", "info1": "something went wrong %s" % e}

    return {"status": 0, "info1": "", "perf1": [], "info2": "", "perf2": [json.dumps(out)]}

def application (environ, start_response):
    from cgi import parse_qs, escape

    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError):
        request_body_size = 0

    data = json.load(environ['wsgi.input'])

    res = validate_input(data)
    if res['status'] == 0:
        res=process_data(data)

    response_body = json.dumps(res)
    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

def main(argv):
    import getopt
    from samana.base import get_dns_ip, ping_host, perf, auth_file
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
            data['warning'] = process_thresholds(a)
        elif o == '-c':
            data['critical'] = process_thresholds(a)
        elif o == '-a':
            (data['auth']['username'], data['auth']['password'], 
                data['auth']['domain']) = auth_file(a)
        elif o == "-i":
            data['id-type'] = a
        elif o == '-h':
            print(usage())
            return 3

    res = validate_input(data)
    if res['status'] == 0:
        res=process_data(data)

    print("%s %s | %s" % (STATUS[res.get('status', 3)], res.get('info1', "UNKNOWN"), res.get('perf1', "")))
    info2 = res.get('info2')
    if info2 is not None and info2 != "":
        print("%s | %s" % (info2, res.get('perf2', "")))
    return res['status']

if __name__ == "__main__":
    import sys
    exit(main(sys.argv))
