#!/usr/bin/python

from winrm.protocol import Protocol
from base64 import b64encode
import json
import sys, getopt
import time
import random
import unicodedata

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
    error = False
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
    if error: exit(error)
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
    print("Username, Domain name and Password are mandatory arguments")
    usage()
    exit(3)

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
  check_winrm.py -H <host name> < -d <user domain name> -u <username> -p <password> | -a <auth file> > -n <nagios>
  check_winrm -h

  <host domain name> Session Host server domain name
  <host name>        Session Host server to be queried
  <domain name>      domain name the Session Host is a member of
  <username>         UPN of the user in the domain with privileges in the Citrix Farm to collect data
  <password>         password of the user with privileges in the Citrix Farm
  <auth file>        file name containing user's credentials
  <nagios>           Nagios server IP
"""
  print(usage)

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
  try:
    opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:n:")

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
      elif o == '-h':
        raise Exception("Unknown argument")

    client = WinRMScript(hostaddress, auth(username, u_domain, password, authfile), nagiosaddress)
    print "OK - Data Collected\n%s" % client.get('samanamon.ps1')
    return 0

  except Exception as err:
    print "UNKNOWN - main Error: " + str(err)
    usage()
    exit(3)

if __name__ == "__main__":
  main()
