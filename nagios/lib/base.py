from .nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
import re
import time

def perf(name, value, warn=None, crit=None, min_val=None, max_val=None):
    convstr = lambda x: str(x) if x is not None else ''
    return "%s=%s;%s;%s;%s;%s" % (
        name, str(value), convstr(warn), convstr(crit), convstr(min_val), convstr(max_val))

def ping_host(ip, count=3):
    import subprocess
    data={
        'packets_sent': 0,
        'packets_received': 0,
        'min': 0,
        'avg': 0,
        'max': 0,
        'mdev': 0
    }
    p = subprocess.Popen(["ping", "-c", str(count), ip], stdout = subprocess.PIPE)
    out = p.communicate()
    packets = None
    rtt = None
    try:
        outstr = out[0].decode('utf8')
        pat = re.search("^(\d+) packets transmitted, (\d+) (packets )?received", outstr, flags=re.M)
        if pat is None:
            raise ValueError("Cannot extract packets from ping output.")
        packets = pat.groups()

        pat = re.search("^(round-trip|rtt) min/avg/max/(stddev|mdev) = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", outstr, flags=re.M)
        if pat is None:
            raise ValueError("Cannot extract ping rtt times.")
        rtt = pat.groups()

        data['packets_sent'] = int(packets[0])
        data['packets_received'] = int(packets[1])
        data['min'] = int(float(rtt[0]))
        data['avg'] = int(float(rtt[1]))
        data['max'] = int(float(rtt[2]))
        data['mdev'] = int(float(rtt[3]))
    except (ValueError, IndexError) as e:
        raise CheckUnknown("Ping output invalid", addl="%s\n%s" % (str(e), outstr))
    except Exception as e:
        raise CheckUnknown("Unexpected Error", addl="%s\n%s\n%s\n%s" % (str(e), outstr, packets, rtt))
    return data

def get_dns_ip(hn):
    import socket

    pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if pat.match(hn):
        return (hn, 0)

    try:
        dns_start = time.time()
        server_data = socket.gethostbyname_ex(hn)
        ips = server_data[2]
        if not isinstance(ips, list) and len(ips) != 1:
            raise ValueError("hostname is linked to more than 1 IP or 0 IPs")
        dns_time = int((time.time() - dns_start) * 1000)

    except ValueError as err:
        raise CheckUnknown("%s" % str(err))
    except IndexError as err:
        raise CheckUnknown("Invalid data received from gethostbyname_ex %s" % str(err), addl=server_data)
    except Exception as err:
        raise CheckCritical("Unable to resove hostname to IP address", addl=str(err))

    return (ips[0], dns_time)


def auth_file(authfile):
    data = {}
    with open(authfile) as f:
        for line in f:
            line = line.strip()
            d = line.split('=')
            if len(d) != 2:
                data[d[0]] = None
            else:
                data[d[0]] = d[1]
    username = data.get('username')
    if username is None:
        raise CheckUnknown("Invalid auth file format. Username not defined.")
    if 'domain' in data and len(data['domain']) > 0 and ('@' in username or '\\' in username):
        raise CheckUnknown("Invalid auth file format. Domain defined multiple times '%s'" % data['domain'])

    return (data.get('username'), data.get('password'), data.get('domain'))
