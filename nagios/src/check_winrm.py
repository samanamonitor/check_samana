#!/usr/bin/python3

import re
from time import time
import traceback
from winrm.protocol import Protocol
from base64 import b64encode
import xml.etree.ElementTree as ET
import socket
import subprocess
from cgi import parse_qs, escape
import json
import sys, getopt

class CheckWinRMExceptionWARN(Exception):
    pass

class CheckWinRMExceptionCRIT(Exception):
    pass

class CheckWinRMExceptionUNKNOWN(Exception):
    pass

class WinRMScript:
    def __init__(self, hostaddress, auth, cleanup=True):
        if auth is None:
            raise CheckWinRMExceptionUNKNOWN("Authentication data missing")
        if 'domain' not in auth or auth['domain'] is None:
            raise CheckWinRMExceptionUNKNOWN("The user domain name is a mandatory argument")
        if 'username' not in auth or auth['username'] is None:
            raise CheckWinRMExceptionUNKNOWN("The username is a mandatory argument")
        if 'password' not in auth or auth['password'] is None:
            raise CheckWinRMExceptionUNKNOWN("The password is a mandatory argument")

        self.cleanup = cleanup
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
        if self.cleanup:
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
 "Done cleanup" | Out-Host''' % { 'scripturl': scripturl, 
      'scriptpath': scriptpath, 
      'scriptname': scriptname,
      'scriptarguments': scriptarguments,
      'hostaddress': self.hostaddress
      }
        else:
            script = '''
 %(scriptpath)s\\%(scriptname)s %(scriptarguments)s| Out-Host
 "Done executing script" | Out-Host''' % {
            'scriptpath': scriptpath, 
            'scriptname': scriptname,
            'scriptarguments': scriptarguments
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
                password=self.password)
            shell_id = p.open_shell()
            encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
            command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand {0}'.format(encoded_ps), ])
            std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
            self.check_error(std_err.decode('ascii'))
            p.cleanup_command(shell_id, command_id)
            p.close_shell(shell_id)

        except Exception as e:
            p.cleanup_command(shell_id, command_id)
            p.close_shell(shell_id)
            raise CheckWinRMExceptionUNKNOWN("Unable to get data from Server (%s) %s." % (type(e).__name__, str(e)))

        if status_code != 0:
            raise CheckWinRMExceptionUNKNOWN(std_err.decode('ascii'))
        return "%s\n%s" % (std_out.decode('ascii'), "")

    def check_error(self, std_err):
        if len(std_err) == 0:
            return
        if std_err[0] == '#':
            temp = std_err.split('\n', 1)
            if len(temp) > 0:
                std_err = temp[1]
        try:
            root = ET.fromstring(std_err)
        except ET.ParseError:
            return
        ns={ 'ps':root.tag.split('}')[0].split('{')[1] }
        msg = "Error executing Powershell Command.\n"
        error = False
        for tag in root.findall('./ps:S', ns):
            t = tag.get('S')
            if t == 'Error':
                error = True
            msg += "%s : %s\n" % (t, tag.text)
        if error:
            raise CheckWinRMExceptionUNKNOWN(msg)

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
        raise CheckWinRMExceptionUNKNOWN("Username missing in authentication file")
    if 'password' not in data:
        raise CheckWinRMExceptionUNKNOWN("Password missing in authentication file")
    if 'domain' not in data and data['username'].find('@') == -1:
        raise CheckWinRMExceptionUNKNOWN("Domain missing in authentication file")
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

def get_dns_ip(hn):
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

def ping_host(ip):
    data={
        'packets_sent': 0,
        'packets_received': 0,
        'min': 0,
        'avg': 0,
        'max': 0,
        'mdev': 0
        }
    packets = None
    rtt = None
    p = subprocess.Popen(["ping", "-c", "3", ip], stdout = subprocess.PIPE)
    out = p.communicate()
    if p.returncode != 0:
        raise CheckWinRMExceptionUNKNOWN("Unable to ping host %s\n%s" % (ip, out[0].decode('ascii')))
    try:
        pat = re.search("^(\d+) packets transmitted, (\d+) received", out[0].decode('ascii'), flags=re.M)
        if pat is None:
            raise ValueError("Cannot extract packets from ping output.")
        packets = pat.groups()

        pat = re.search("^r[^ ]+ min/avg/max/[^ ]+ = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", out[0].decode('ascii'), flags=re.M)
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
        raise CheckWinRMExceptionUNKNOWN("Ping output invalid. %s\n%s" % (str(e), out[0]))

    except Exception as e:
        raise Exception("unexpected error %s\n%s\n%s\n%s" % (str(e), out[0], packets, rtt))

    return data

def process_data(data):
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
    try:
        if data['hostaddress'] is None:
            raise CheckWinRMExceptionUNKNOWN("Invalid Host address")

        if data['nagiosaddress'] is None and data['url'] is None:
            raise CheckWinRMExceptionUNKNOWN("Powershell script location not defined.")

        if data['url'] is None:
            data['url'] = "http://%s/%s" % (data['nagiosaddress'], data['script'])
        #TODO check URL syntax for the case when we receive URL from user

        user_auth = auth(data['username'], data['u_domain'], data['password'], data['authfile'])
        if user_auth is None:
            raise CheckWinRMExceptionUNKNOWN("Invalid authentication information")

        if data['warning'] is not None:
            try:
                (dns_warn, ping_warn, packet_loss_warn, winrm_warn) = data['warning'].split(',')
                dns_warn = int(dns_warn)
                ping_warn = int(ping_warn)
                packet_loss_warn = int(packet_loss_warn)
                winrm_warn = int(winrm_warn)
            except ValueError:
                raise CheckWinRMExceptionUNKNOWN("Invalid Warning values")

        if data['critical'] is not None:
            try:
                (dns_crit, ping_crit, packet_loss_crit, winrm_crit) = data['critical'].split(',')
                dns_crit = int(dns_crit)
                ping_crit = int(ping_crit)
                packet_loss_crit = int(packet_loss_crit)
                winrm_crit = int(winrm_crit)
            except ValueError:
                raise CheckWinRMExceptionUNKNOWN("Invalid Critical values")

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

        response_data = {
            'status': 0,
            'message': "OK - Data Collected | %s\n%s\n%s" % (perf_data, out, data)
            }


    except CheckWinRMExceptionWARN as e:
        response_data = {
            'status': 1,
            'message': "WARNING - %s" % e
            }

    except CheckWinRMExceptionCRIT as e:
        response_data = {
            'status': 2,
            'message': "CRITICAL - %s" % e
            }

    except CheckWinRMExceptionUNKNOWN as e:
        response_data = {
            'status': 3,
            'message': "UNKNOWN - %s" % e
            }

    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        response_data = {
            'status': 3,
            'message': "UNKNOWN - %s at %s\n%s" % (e, tb.tb_lineno, traceback_info)
            }

    return response_data

def usage():
  usage = """Check WinRM v2.0.0
 This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
 SAMANA GROUP LLC. If you want to use it, you should contact us before
 to get a license.
 Copyright (c) 2019 Samana Group LLC

 Usage:
  check_winrm.py -H <host name> < -d <user domain name> -u <username> -p <password> | -a <auth file> > (-n <nagios> -s <script name> | -U <script URL>) [ -A "<script arguments in quotes>"] [-w <name resolution time warn (ms)>,<ping rtt warn (ms)>,<ping packet loss %>,<winrm time warn (ms)>] [-c <name resolution crit (ms)><ping rtt crit (ms)>,<ping packet loss %>,<warn time crit (ms)>]
  check_winrm -h

  <host domain name> Session Host server domain name
  <host name>        Session Host server to be queried
  <domain name>      domain name the Session Host is a member of
  <username>         UPN of the user in the domain with privileges in the Citrix Farm to collect data
  <password>         password of the user with privileges in the Citrix Farm
  <auth file>        file name containing user's credentials
  <nagios>           Nagios server IP
  <script>           Powershell script to run on server
  <script URL>       URL where Powershell script is located
  <name resolution>  Time to resolve the host name in miliseconds. Only integer values accepted.
  <ping rtt>         Ping round trip time in miliseconds. Only integer values accepted.
  <ping packet loss> \% of packets that can be lost. Don't use \% sign in value
  <winrm time>       WinRM execution time in miliseconds. Only integer values accepted."""
  print(usage)

def application (environ, start_response):
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
        'cleanup': True
    }

    d = parse_qs(environ['QUERY_STRING'])
    for k in data.keys():
        data[k] = d.get(k, [ None ])[0]
    response_body = json.dumps(process_data(data))

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

def main():
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
        'cleanup': True
    }
    opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:n:s:w:c:U:A:C")

    for o, a in opts:
        if o == '-H':
            data['hostaddress'] = a
        elif o == '-d':
            data['u_domain'] = a
        elif o == '-u':
            data['username'] = a
        elif o == '-p':
            data['password'] = a
        elif o == '-a':
            data['authfile'] = a
        elif o == '-n':
            data['nagiosaddress'] = a
        elif o == '-s':
            data['script'] = a
        elif o == '-w':
            data['warning'] = a
        elif o == '-c':
            data['critical'] = a
        elif o == '-U':
            data['url'] = a
        elif o == '-A':
            data['scriptarguments'] = a
        elif o == '-C':
            data['cleanup'] = False
        else:
            usage()
            exit(3)

    response_data = process_data(data)

    print(response_data['message'])
    exit(response_data['status'])

if __name__ == "__main__":
  main()
