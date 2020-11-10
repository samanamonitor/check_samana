#!/usr/bin/python

from winrm.protocol import Protocol
from base64 import b64encode
import json
import sys, getopt
import time
import random
import unicodedata
import re
from time import time

class WinRMScript:
  def __init__(self, hostaddress, auth, nagiosaddress):
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
    self.nagiosaddress = nagiosaddress
    if 'upn' in auth:
      self.username = auth['username']
    else:
      self.username = auth['domain'] + '\\' + auth['username']
    self.password = auth['password']

  def get(self, scriptname):
    scriptpath = "c:\\samanamon"
    scripturl="http://%s/%s" % (self.nagiosaddress, scriptname)
    script = '''
if (-Not (Test-Path %(scriptpath)s)) { mkdir %(scriptpath)s | Out-Null}
"Environment prepared." | Out-Host
Invoke-WebRequest -Uri %(scripturl)s -OutFile "%(scriptpath)s\\%(scriptname)s"
if (-Not (Test-Path %(scriptpath)s\\%(scriptname)s)) { 
  "File not downloaded" | Out-Host; 
  rmdir %(scriptpath)s
  exit 1 
}
"Downloaded Script." | Out-Host
%(scriptpath)s\\%(scriptname)s | Out-Host
"Done executing script" | Out-Host
del %(scriptpath)s\\%(scriptname)s
rmdir %(scriptpath)s
"Done cleanup" | Out-Host
''' % { 'scripturl': scripturl, 
      'scriptpath': scriptpath, 
      'scriptname': scriptname,
      'hostaddress': self.hostaddress,
      'nagiosaddress': self.nagiosaddress
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

def auth_file(authfile):
  data = {}
  try:
    with open(authfile) as f:
      linenum = 0
      for l in f:
        linenum += 1
        line = l.split("#")[0]
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
  except Exception as e:
    print "UNKNOWN - auth_file Error " + str(e)
    exit(3)

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

def usage():
  usage = """Check WinRM v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2019 Samana Group LLC

Usage:
  check_winrm.py -H <host name> < -d <user domain name> -u <username> -p <password> | -a <auth file> > -n <nagios> [-w <name resolution time warn (ms)>,<ping rtt warn (ms)>,<ping packet loss %>,<winrm time warn (ms)>] [-c <name resolution crit (ms)><ping rtt crit (ms)>,<ping packet loss %>,<warn time crit (ms)>]
  check_winrm -h

  <host domain name> Session Host server domain name
  <host name>        Session Host server to be queried
  <domain name>      domain name the Session Host is a member of
  <username>         UPN of the user in the domain with privileges in the Citrix Farm to collect data
  <password>         password of the user with privileges in the Citrix Farm
  <auth file>        file name containing user's credentials
  <nagios>           Nagios server IP
  <name resolution>  Time to resolve the host name in miliseconds. Only integer values accepted.
  <ping rtt>         Ping round trip time in miliseconds. Only integer values accepted.
  <ping packet loss> \% of packets that can be lost. Don't use \% sign in value
  <winrm time>       WinRM execution time in miliseconds. Only integer values accepted.
"""
  print(usage)

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
    dns_end = time()
    return (ips[0], dns_end-dns_start)

  except ValueError as err:
    print "CRITICAL - %s" % str(err)
    exit(2)
  except IndexError as err:
    print "CRITICAL - invalid data received from gethostbyname_ex %s\n%s" % (str(err), server_data)
    exit(2)    
  except Exception as err:
    print "CRITICAL - Unable to resove hostname to IP address\n%s" % str(err)
    exit(2)


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
    print "UNKNOWN - ping output invalid %s\n%s" % (str(e), out[0])
    exit(3)
  except Exception as e:
    print "UNKNOWN - unexpected error %s\n%s\n%s\n%s" % (str(e), out[0], packets, rtt)
    exit(3)
  return data

def main():
  u_domain = None
  hostaddress = None
  h_domain = None
  username = None
  password = None
  module = None
  warn = None
  crit = None
  DeliveryGroup = None
  authfile = None
  load_from_server = False
  nagiosaddress = None
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
  script = 'samanamon.ps1'

  try:
    opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:n:s:w:c:")

    for o, a in opts:
      if o == '-H':
        hostaddress = a
      elif o == '-d':
        u_domain = a
      elif o == '-u':
        username = a
      elif o == '-p':
        password = a
      elif o == '-a':
        authfile = a
      elif o == '-n':
        nagiosaddress = a
      elif o == '-s':
        script = a
      elif o == '-w':
        warning = a
      elif o == '-c':
        critical = a
      elif o == '-h':
        raise Exception("Unknown argument")

    if hostaddress is None:
      print "UNKNOWN - Hostaddress not defined."
      exit(3)

    if nagiosaddress is None:
      print "UNKNOWN - Nagios address not defined."
      exit(3)

    user_auth = auth(username, u_domain, password, authfile)
    if user_auth is None:
      print "UNKNOWN - Invalid authentication information"
      exit(3)

    if warning is not None:
      try:
        (dns_warn, ping_warn, packet_loss_warn, winrm_warn) = warning.split(',')
        dns_warn = int(dns_warn)
        ping_warn = int(ping_warn)
        packet_loss_warn = int(packet_loss_warn)
        winrm_warn = int(winrm_warn)
      except ValueError:
        print "UNKNOWN - Invalid Warning values"
        usage()
        exit(3)
    if critical is not None:
      try:
        (dns_crit, ping_crit, packet_loss_crit, winrm_crit) = critical.split(',')
        dns_crit = int(dns_crit)
        ping_crit = int(ping_crit)
        packet_loss_crit = int(packet_loss_crit)
        winrm_crit = int(winrm_crit)
      except ValueError:
        print "UNKNOWN - Invalid Critical values"
        usage()
        exit(3)

    (hostip, dns_time) = get_dns_ip(hostaddress)
    ping_data = ping_host(hostip)

    winrm_start = time()
    client = WinRMScript(hostaddress, user_auth, nagiosaddress)
    out = client.get(script)
    winrm_time = time() - winrm_start

    perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])

    perf_data = "dns_resolution=%d;;;; ping_perc_packet_loss=%d;;;; ping_rtt=%d;;;; winrm_time=%d;;;;" % \
      (dns_time, perc_packet_loss, ping_data['avg'], winrm_time)

    if dns_crit is not None and dns_crit < dns_time:
      print "CRITICAL - DNS name resolution took longer than expected %d | %s\n%s." % \
        (dns_time, perf_data, out)
      exit(2)
    if dns_warn is not None and dns_warn < dns_time:
      print "WARNING - DNS name resolution took longer than expected %d | %s\n%s." % \
        (dns_time, perf_data, out)
      exit(1)
    if packet_loss_crit is not None and packet_loss_crit < perc_packet_loss:
      print "CRITICAL - PING lost %d\% packets | %s\n%s" % \
        (perc_packet_loss, perf_data, out)
      exit(2)
    if packet_loss_warn is not None and packet_loss_warn < perc_packet_loss:
      print "WARNING - PING lost %d\% packets | %s\n%s" % \
        (perc_packet_loss, perf_data, out)
      exit(1)
    if ping_crit is not None and ping_crit < ping_data['avg']:
      print "CRITICAL - PING rtt is greater than expected %d ms | %s\n%s" % \
        (ping_data['avg'], perf_data, out)
      exit(2)
    if ping_warn is not None and ping_warn < ping_data['avg']:
      print "WARNING - PING rtt is greater than expected %d ms | %s\n%s" % \
        (ping_data['avg'], perf_data, out)
      exit(1)
    if winrm_crit is not None and winrm_crit < winrm_time:
      print "CRITICAL - WinRM took longer than expected %d ms | %s\n%s" % \
        (winrm_time, perf_data, out)
      exit(2)
    if winrm_warn is not None and winrm_warn < winrm_time:
      print "WARNING - WinRM took longer than expected %d ms | %s\n%s" % \
        (winrm_time, perf_data, out)
      exit(1)

    print "OK - Data Collected | %s\n%s" % \
        (perf_data, out)
    exit(0)

  except Exception as err:
    exc_type, exc_obj, tb = sys.exc_info()
    print "UNKNOWN - main Error: %s at line %s" % \
      (str(err), tb.tb_lineno)
    usage()
    exit(3)

if __name__ == "__main__":
  main()
