#!/usr/bin/python

from pymongo import MongoClient
from winrm.protocol import Protocol
from base64 import b64encode
import json
import sys, getopt
import time
import random
import unicodedata

class CitrixXD:
  def __init__(self, ddc, auth, refresh_interval, load_from_server):
    try:
      if ddc is None: 
        raise Exception("The DDC is a mandatory argument")
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

    self.ddc = ddc
    if auth['upn']:
      self.username = auth['username']
    else:
      self.username = auth['domain'] + '\\' + auth['username']
    self.password = auth['password']
    self.refresh_interval = refresh_interval
    self.citrix = MongoClient().citrix
    timer = self.citrix[self.ddc].timers.find_one({"module": "apps"})

    if timer is not None:
        last_update = timer['last_update']
    else:
        last_update = None;

    if last_update is not None:
        r = pow((time.time() - last_update)/float(refresh_interval), 5) * random.random()
    if load_from_server and (last_update is None or r > 0.5):
      self.updateCache()

  def getCitrix(self):
    script = """
#Clear
Add-PSSnapin Citrix.*
$m = Get-BrokerApplication
$json = ConvertTo-JSON -compress $m #| Out-File $file
$json
"""

    shell_id = None
    command_id = None
    p = None
    error = False
    try:
      p = Protocol(
        endpoint='https://' + self.ddc + ':5986/wsman',
        transport='ntlm',
        username=self.username,
        password=self.password,
        server_cert_validation='ignore')
      shell_id = p.open_shell()
      encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
      command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand {0}'.format(encoded_ps), ])
      std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
      citrix = json.loads(std_out, 'latin-1')
    except Exception as e:
      print("UNKNOWN - Unable to get data from Citrix DDC (%s) %s." % (str(e), type(e).__name__))
      error = True
    finally:
      p.cleanup_command(shell_id, command_id)
      p.close_shell(shell_id)
    if error: exit(3)
    return citrix

  def updateCache(self):
    try:
        self.citrix[self.ddc].timers.update({"module": "apps"}, \
            {"$set": {"last_update": time.time() }}, \
            upsert=True)
        self.citrix[self.ddc].apps.drop()
        for a in self.getCitrix():
            self.citrix[self.ddc].apps.insert(a)
    except OSError as err:
      print("UNKNOWN - Unable to save cache {0}".format(err))
      exit(3)

  def getRawData(self, hostname, domain):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)
    if s is None:
      print("UNKNOWN - {0} is not part of the citrix farm".format(MachineName))
      exit(3)
    print(json.dumps(s))
    exit(0)

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
        if len(d) != 2: raise Exception("Syntax error in authentication file at line %d" % linenum)
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
    print "UNKNOWN - Error " + str(e)
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
  usage = """Check Citrix DDC v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2017 Samana Group LLC

Usage:
  check_ctx_apps.py -D <ddc> < -d <user domain name> -u <username> -p <password> | -a <auth file> > [-r <refresh interval>] -w <warning> -c <critical> -l
  check_ctx_apps.py -h

  <ddc> Citrix Desktop Deliver Controller hostname or IP address
  <host domain name> Session Host server domain name
  <domain name> domain name the Session Host is a member of
  <username> UPN of the user in the domain with privileges in the Citrix Farm to collect data
  <password> password of the user with privileges in the Citrix Farm
  <auth file> file name containing user's credentials
  <refresh interval> Seconds to keep cache of the farm locally. default=120
  -l loads data from server. By default data is fetched from cache
"""
  print(usage)

def main():
  refresh_interval = 120
  ddc = None
  u_domain = None
  hostname = None
  h_domain = None
  username = None
  password = None
  warn = None
  crit = None
  authfile = None
  load_from_server = False
  try:
    
    opts, args = getopt.getopt(sys.argv[1:], "D:d:u:p:hw:c:a:r:l")

    for o, a in opts:
      if o == '-D':
        ddc = a
      elif o == '-d':
        u_domain = a
      elif o == '-u':
        username = a
      elif o == '-p':
        password = a
      elif o == '-w':
        warn = a
      elif o == '-c':
        crit = a
      elif o == '-a':
        authfile = a
      elif o == '-r':
        refresh_interval = int(a)
      elif o == '-l':
        load_from_server = True
      elif o == '-h':
        raise Exception("Unknown argument")

    apps = CitrixXD(ddc, auth(username, u_domain, password, authfile), refresh_interval, load_from_server)

    if load_from_server:
      print "OK - Data loaded"
      for a in apps.citrix[apps.ddc].apps.find():
         print "{0}={1}".format(a['ApplicationName'], a['Enabled'])
      exit(0)
    else:
      raise Exception("Module not implemented")

  except Exception as err:
    print "UNKNOWN - Error: " + str(err)
    usage()
    exit(3)

if __name__ == "__main__":
  main()
