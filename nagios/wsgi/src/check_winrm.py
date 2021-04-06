from winrm.protocol import Protocol
from base64 import b64encode
import json
import sys, getopt
import time
import random
import unicodedata
import re
from time import time
from cgi import parse_qs, escape


class CheckWinRMExceptionWARN(Exception):
    pass

class CheckWinRMExceptionCRIT(Exception):
    pass

class WinRMScript:
  def __init__(self, hostaddress, auth):
    try:
      if auth is None:
        raise Exception("Authentication data missing")
      if 'domain' not in auth or auth['domain'] is None:
        raise Exception("The user domain name is a mandatory argument")
      if 'username' not in auth or auth['username'] is None:
        raise Exception("The username is a mandatory argument")
      if 'password' not in auth or auth['password'] is None:
        raise Exception("The password is a mandatory argument")

    except Exception as e:
      print "UNKNOWN - Error " + str(e)
      usage()
      exit(3)

    self.data = {}
    self.hostaddress = hostaddress
    if 'upn' in auth:
      self.username = auth['username']
    else:
      self.username = auth['domain'] + '\\' + auth['username']
    self.password = auth['password']

  def run(self, scripturl, scriptarguments):
    scriptpath = "c:\\samanamon"
    #scripturl="http://%s/%s" % (self.nagiosaddress, scriptname)
    scriptname = scripturl.split('/')[-1]
    script = '''
if (-Not (Test-Path %(scriptpath)s)) { mkdir %(scriptpath)s | Out-Null}
"Environment prepared." | Out-Host
Invoke-WebRequest -Uri %(scripturl)s -OutFile "%(scriptpath)s\\%(scriptname)s"
if (-Not (Test-Path %(scriptpath)s\\%(scriptname)s)) { 
  "File not downloaded" | Out-Host; 
  Remove-Item -Recurse -Force %(scriptpath)s
  exit 1 
}
"Downloaded Script." | Out-Host
%(scriptpath)s\\%(scriptname)s %(scriptarguments)s| Out-Host
"Done executing script" | Out-Host
del %(scriptpath)s\\%(scriptname)s
Remove-Item -Recurse -Force %(scriptpath)s
"Done cleanup" | Out-Host
''' % { 'scripturl': scripturl, 
      'scriptpath': scriptpath, 
      'scriptname': scriptname,
      'scriptarguments': scriptarguments,
      'hostaddress': self.hostaddress
      }

    shell_id = None
    command_id = None
    p = None
    error = 0
    std_out = ''
    std_err = ''
    try:
      p = Protocol(
        endpoint='http://%s:5985/wsman' % self.hostaddress,
        transport='ntlm',
        username=self.username,
        password=self.password,
        server_cert_validation='ignore')
      shell_id = p.open_shell()
      encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
      command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand {0}'.format(encoded_ps), ])
      std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
      if status_code != 0:
        print("ERROR - %s" % std_err)
        error = 1
    except Exception as e:
      print("UNKNOWN - Unable to get data from Server (%s) %s." % (str(e), type(e).__name__))
      error = 3
    finally:
      p.cleanup_command(shell_id, command_id)
      p.close_shell(shell_id)
    if error > 0: exit(error)
    return std_out

def get_dns_ip(hn):
  import socket

  pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
  if pat.match(hn):
    return (hn, 0)

  try:
    dns_start = time()
    server_data = socket.gethostbyname_ex(hn)
    ips = server_data[2]
    if not isinstance(ips, list) and len(ips) != 1:
      raise ValueError("hostname is linked to more than 1 IP or 0 IPs")
    dns_time = (time() - dns_start) * 1000
    return (ips[0], dns_time)

  except ValueError as err:
    raise CheckWinRMExceptionCRIT(str(err))

  except IndexError as err:
    raise CheckWinRMExceptionCRIT("Invalid data received from gethostbyname_ex %s\n%s" % (str(err), server_data))

  except Exception as err:
    raise CheckWinRMExceptionCRIT("Unable to resove hostname to IP address\n%s" % str(err))

def auth_file(authfile):
    data = {}
    with open(authfile) as f:
      linenum = 0
      for l in f:
        linenum += 1
        line = l #.split("#")[0]
        line = line.strip()
        d = line.split('=')
        if len(d) != 2: continue
        data[d[0]] = d[1]

    if 'username' not in data:
        raise Exception("Username missing in authentication file")
    if 'password' not in data:
        raise Exception("Password missing in authentication file")
    if 'domain' not in data and data['username'].find('@') == -1:
        raise Exception("Domain missing in authentication file")
    if 'domain' not in data or data['username'].find('@') != -1:
        data['upn'] = True
    else:
        data['upn'] = False
    return data

def auth(username, domainname, password, authfile):
    if authfile is not None:
        return auth_file(authfile)

    if username is None or domainname is None or password is None:
        return None

    return {
        'username': username,
        'domain': domainname,
        'password': password
        }

def ping_host(ip):
    import subprocess
    data={
        'packets_sent': 0,
        'packets_received': 0,
        'min': 0,
        'avg': 0,
        'max': 0,
        'mdev': 0
        }
    p = subprocess.Popen(["ping", "-c", "3", ip], stdout = subprocess.PIPE)
    out = p.communicate()
    try:
        pat = re.search("^(\d+) packets transmitted, (\d+) received", out[0], flags=re.M)
        if pat is None:
            raise ValueError("Cannot extract packets from ping output.")
        packets = pat.groups()

        pat = re.search("^rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", out[0], flags=re.M)
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
        raise Exception("UNKNOWN - Ping output invalid. %s\n%s" % (str(e), out[0]))

    except Exception as e:
        raise Exception("UNKNOWN - unexpected error %s\n%s\n%s\n%s" % (str(e), out[0], packets, rtt))

    return data


def application ( environ, start_response):
    warning = None
    critical = None
    ping_warn = None
    ping_crit = None
    winrm_warn = None
    winrm_crit = None
    dns_warn = None
    dns_crit = None
    packet_loss_warn = None
    packet_loss_crit = None

    data = {
        'hostaddress': None,
        'u_domain': None,
        'username': None,
        'password': None,
        'authfile': None,
        'nagiosaddress': None,
        'script': None,
        'warning': None,
        'critical': None,
        'url': None,
        'scriptarguments': None,
    }

    d = parse_qs(environ['QUERY_STRING'])
    for k in data.keys():
        data[k] = d.get(k, [ None ])[0]

    try:
        if data['hostaddress'] is None:
            raise Exception("Invalid Host address")

        if data['nagiosaddress'] is None and data['url'] is None:
            raise Exception("UNKNOWN - Powershell script location not defined.")

        if data['url'] is None:
            data['url'] = "http://%s/%s" % (data['nagiosaddress'], data['script'])
        #TODO check URL syntax for the case when we receive URL from user

        user_auth = auth(data['username'], data['u_domain'], data['password'], data['authfile'])
        if user_auth is None:
            raise Exception("UNKNOWN - Invalid authentication information")

        if data['warning'] is not None:
            try:
                (dns_warn, ping_warn, packet_loss_warn, winrm_warn) = data['warning'].split(',')
                dns_warn = int(dns_warn)
                ping_warn = int(ping_warn)
                packet_loss_warn = int(packet_loss_warn)
                winrm_warn = int(winrm_warn)
            except ValueError:
                raise Exception("UNKNOWN - Invalid Warning values")

        if data['critical'] is not None:
            try:
                (dns_crit, ping_crit, packet_loss_crit, winrm_crit) = data['critical'].split(',')
                dns_crit = int(dns_crit)
                ping_crit = int(ping_crit)
                packet_loss_crit = int(packet_loss_crit)
                winrm_crit = int(winrm_crit)
            except ValueError:
                raise Exception("UNKNOWN - Invalid Critical values")

        (hostip, dns_time) = get_dns_ip(data['hostaddress'])
        ping_data = ping_host(hostip)

        winrm_start = time()
        client = WinRMScript(data['hostaddress'], user_auth)
        out = client.run(data['url'], data['scriptarguments'])
        winrm_time = (time() - winrm_start) * 1000

        perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])

        perf_data = "dns_resolution=%d;%s;%s;; ping_perc_packet_loss=%d;%s;%s;; ping_rtt=%d;%s;%s;; winrm_time=%d;%s;%s;;" % \
            (dns_time, dns_warn if dns_warn is not None else '', dns_crit if dns_crit is not None else '',
                perc_packet_loss, packet_loss_warn if packet_loss_warn is not None else '', packet_loss_crit if packet_loss_crit is not None else '',
                ping_data['avg'], ping_warn if ping_warn is not None else '', ping_crit if ping_crit is not None else '', 
                winrm_time, winrm_warn if winrm_warn is not None else '', winrm_crit if winrm_crit is not None else '')

        if dns_crit is not None and dns_crit < dns_time:
            raise CheckWinRMExceptionCRIT("DNS name resolution took longer than expected %d | %s\n%s." % \
                (dns_time, perf_data, out))

        if dns_warn is not None and dns_warn < dns_time:
            raise CheckWinRMExceptionWARN("DNS name resolution took longer than expected %d | %s\n%s." % \
            (dns_time, perf_data, out))

        if packet_loss_crit is not None and packet_loss_crit < perc_packet_loss:
            raise CheckWinRMExceptionCRIT("PING lost %d\% packets | %s\n%s" % \
            (perc_packet_loss, perf_data, out))

        if packet_loss_warn is not None and packet_loss_warn < perc_packet_loss:
            raise CheckWinRMExceptionWARN("PING lost %d\% packets | %s\n%s" % \
            (perc_packet_loss, perf_data, out))

        if ping_crit is not None and ping_crit < ping_data['avg']:
            raise CheckWinRMExceptionCRIT("PING rtt is greater than expected %d ms | %s\n%s" % \
            (ping_data['avg'], perf_data, out))

        if ping_warn is not None and ping_warn < ping_data['avg']:
            raise CheckWinRMExceptionWARN("PING rtt is greater than expected %d ms | %s\n%s" % \
            (ping_data['avg'], perf_data, out))

        if winrm_crit is not None and winrm_crit < winrm_time:
            raise CheckWinRMExceptionCRIT("WinRM took longer than expected %d ms | %s\n%s" % \
            (winrm_time, perf_data, out))

        if winrm_warn is not None and winrm_warn < winrm_time:
            raise CheckWinRMExceptionWARN("WinRM took longer than expected %d ms | %s\n%s" % \
            (winrm_time, perf_data, out))

        response_body = json.dumps({
            'status': 0,
            'message': "OK - Data Collected | %s\n%s" % (perf_data, out)
            })


    except CheckWinRMExceptionWARN as e:
        response_body = json.dumps({
            'status': 1,
            'message': "WARNING - %s" % e
            })

    except CheckWinRMExceptionCRIT as e:
        response_body = json.dumps({
            'status': 2,
            'message': "CRITICAL - %s" % e
            })

    except Exception as e:
        response_body = json.dumps({
            'status': 3,
            'message': "UNKNOWN - %s" % e
            })

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]

    start_response(status, response_headers)

    return [response_body]