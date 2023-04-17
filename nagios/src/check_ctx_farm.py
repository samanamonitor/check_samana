#!/usr/bin/python3

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
      print("UNKNOWN - Error %s" % str(e))
      usage()
      exit(3)

    self.data = {}
    self.ddc = ddc
    if 'upn' in auth:
      self.username = auth['username']
    else:
      self.username = auth['domain'] + '\\' + auth['username']
    self.password = auth['password']
    self.refresh_interval = refresh_interval

    self.getCache()
    if 'time' in self.data:
      last_update = self.data['time']
      r = pow((time.time() - last_update)/float(refresh_interval), 5) * random.random()
    else:
      last_update = None
      r = 0

#    if load_from_server and (last_update is None or r > 0.5):
    if load_from_server:
      self.updateCache()

  def getCache(self):
    try:
      F = open('/tmp/' + self.ddc + '_citrix.json', "r")
      self.data = json.load(F)
      F.close()
    except IOError:
      self.updateCache()

  def getCitrix(self):
    script = """
Add-PSSnapin Citrix.*
$m = Get-BrokerMachine -MaxRecordCount 5000
$json = ConvertTo-JSON -compress $m
$json
"""

    shell_id = None
    command_id = None
    p = None
    error = False
    try:
      from winrm.protocol import Protocol
      p = Protocol(
        endpoint='http://' + self.ddc + ':5985/wsman',
        transport='ntlm',
        username=self.username,
        password=self.password,
        server_cert_validation='ignore')
      shell_id = p.open_shell()
      encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
      command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand {0}'.format(encoded_ps), ])
      std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
      citrix = json.loads(std_out.decode('ascii'))
      if not isinstance(citrix, list):
        citrix = [citrix]
    except Exception as e:
      print("UNKNOWN - Unable to get data from Citrix DDC (%s) %s." % (str(e), type(e).__name__))
      error = True
    finally:
      p.cleanup_command(shell_id, command_id)
      p.close_shell(shell_id)
    if error: exit(3)
    return citrix

  def saveCache(self):
    try:
      F = open('/tmp/' + self.ddc + '_citrix.json', "w")
      F.write(json.dumps(self.data))
      F.close()
    except OSError as err:
      print("UNKNOWN - Unable to save cache {0}".format(err))
      exit(3)

  def updateCache(self):
    self.data['time'] = time.time()
    for m in self.getCitrix():
      if 'MachineName' not in m: continue
      mn = m['MachineName'].split('\\')
      if len(mn) == 2:
          name = mn[0] + '__' + mn[1]
      else:
          print("Invalid Machine name %s" % m['MachineName'])
          continue
      if self.data.get(name):
        if m['InMaintenanceMode'] != self.data[name]['data']['InMaintenanceMode']:
          self.data[name]['LastChangeInMaintenanceMode'] = self.data['time']
        if m['RegistrationState'] != self.data[name]['data']['RegistrationState']:
          self.data[name]['LastChangeRegistrationState'] = self.data['time']
        if m['LoadIndex'] != self.data[name]['data']['LoadIndex']:
          self.data[name]['LastChangeLoadIndex'] = self.data['time']
      else:
        self.data[name] = {}
        self.data[name]['LastChangeInMaintenanceMode'] = self.data['time']
        self.data[name]['LastChangeRegistrationState'] = self.data['time']
        self.data[name]['LastChangeLoadIndex'] = self.data['time']
      self.data[name]['data'] = m

    self.saveCache()

  def getMachineName(self, hostname, domain):
    if hostname is None:
      print("UNKNOWN - hostname argument is necessary for this module")
      exit(3)
    if domain is None:
      print("UNKNOWN - domain argument is necessary for this module")
      exit(3)

    return domain + "__" + hostname

  def getRawData(self, hostname, domain):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)
    if s is None:
      print("UNKNOWN - {0} is not part of the citrix farm".format(MachineName))
      exit(3)
    print(json.dumps(s))
    exit(0)

  def getInMaintenance(self, hostname, domain, warn, crit):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)
    if s is None:
      print("UNKNOWN - {0} is not part of the citrix farm".format(MachineName))
      exit(3)

    if s['data']['InMaintenanceMode'] == True:
      timeInMaintenanceMode = int((self.data['time'] - s['LastChangeInMaintenanceMode'])/60)
      if crit is not None and timeInMaintenanceMode > int(crit):
        print("CRITICAL - Server has been {0} minutes in maintenance mode ".format(timeInMaintenanceMode) + \
            "| maintenance={0};{1};{2};;".format(timeInMaintenanceMode, warn, crit))
        exit(2)
      elif warn is not None and timeInMaintenanceMode > int(warn):
        print("WARNING - Server has been {0} minutes in maintenance mode ".format(timeInMaintenanceMode) + \
            "| maintenance={0};{1};{2};;".format(timeInMaintenanceMode, warn, crit))
        exit(1)
      else:
        print("OK - Server has been {0} minutes in maintenance mode ".format(timeInMaintenanceMode) + \
                    "| maintenance={0};{1};{2};;".format(timeInMaintenanceMode, warn, crit))
        exit(0)
    else:
        print("OK - Server is not in maintenance mode " + \
            "| maintenance={0};{1};{2};;".format(0, warn, crit))
        exit(0)

  def getRegistrationState(self, hostname, domain, warn, crit):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)
    if s is None:
      print("UNKNOWN - {0} is not part of the citrix farm".format(MachineName))
      exit(3)

    if s['data']['RegistrationState'] != 2:
      timeUnregistered = int((self.data['time'] - s['LastChangeRegistrationState'])/60)
      if crit is not None and timeUnregistered > int(crit):
        print("CRITICAL - Server has been {0} minutes unregistered ".format(timeUnregistered) + \
            "| unregistered={0};{1};{2};;".format(timeUnregistered, int(warn), int(crit)))
        exit(2)
      elif warn is not None and timeUnregistered > int(warn):
        print("WARNING - Server has been {0} minutes unregistered ".format(timeUnregistered) + \
            "| unregistered={0};{1};{2};;".format(timeUnregistered, int(warn), int(crit)))
        exit(1)
      else:
        print("OK - Server has been {0} minutes unregistered ".format(timeUnregistered) + \
            "| unregistered={0};{1};{2};;".format(timeUnregistered, int(warn), int(crit)))
        exit(0)
    else:
      print("OK - Server is registered " + \
            "| unregistered={0};{1};{2};;".format(0, int(warn), int(crit)))
      exit(0)

  def getLoad(self, hostname, domain, warn, crit):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)

    status = "UNKNOWN"
    code = 3
    if s is None:
      print("{0} - {1} is not part of the citrix farm".format(status, MachineName))
      exit(code)

    if crit is None:
      crit = ''
    if warn is None:
      warn = ''

    if warn != '' and crit != '' and int(warn) > int(crit):
      print("{0} - Warning cannot be higher than Critical".format(status))
      exit(code)

    load = s['data']['LoadIndex']
    perf_data = "'load'={1};{2};{3};0;10000" % (load, warn, crit)
    for i in s['data']['LoadIndexes']:
      (index_name, index_value) = i.split(':')
      index_name = unicodedata.normalize('NFKD', index_name).encode('ascii', 'ignore').translate(None, '$')
      #out = "{0} '{1}'={2};;;0;10000".format(out, index_name, index_value)
      print("{0} load is {1}".format(index_name, index_value))
    #print out


    #for a in s['data']['LoadIndexes']
    if crit != '' and load > int(crit):
      status = "CRITICAL"
      code = 2
    elif warn != '' and load > int(warn):
      status = "WARNING"
      code = 1
    else:
      status = "OK"
      code = 0
    #out = "{0} - Server is at {1} Load | 'load'={1};{2};{3};0;10000 ".format(status, load, warn, crit)
    print("{0} - Server is at {1} Load | {2}".format(status, perf_data))
    #print("Individual Data; | ")
    for i in s['data']['LoadIndexes']:
      (index_name, index_value) = i.split(':')
      index_name = unicodedata.normalize('NFKD', index_name).encode('ascii', 'ignore').translate(None, '$')
      #out = "{0} '{1}'={2};;;0;10000".format(out, index_name, index_value)
      print("{0} load is {1}".format(index_name, index_value))
    #print out
    exit(code)

  def getLoadIndex(self, hostname, domain, warn, crit):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)

    status = "UNKNOWN"
    code = 3
    if s is None:
      print("{0} - {1} is not part of the citrix farm".format(status, MachineName))
      exit(code)

    if crit is None:
      crit = ''
    if warn is None:
      warn = ''

    if warn != '' and crit != '' and int(warn) > int(crit):
      print("{0} - Warning cannot be higher than Critical".format(status))
      exit(code)

    load = s['data']['LoadIndex']
    if crit != '' and load > int(crit):
      status = "CRITICAL"
      code = 2
    elif warn != '' and load > int(warn):
      status = "WARNING"
      code = 1
    else:
      status = "OK"
      code = 0
    #out = "{0} - Server is at {1} Load | 'load'={1};{2};{3};0;10000 ".format(status, load, warn, crit)
    print("{0} - Server is at {1} Load | 'load'={1};{2};{3};0;10000".format(status, load, warn, crit))
    #print("Individual Data; | ")
    for i in s['data']['LoadIndexes']:
      (index_name, index_value) = i.split(':')
      #index_name = unicodedata.normalize('NFKD', index_name).encode('ascii', 'ignore').translate(None, '$')
      #out = "{0} '{1}'={2};;;0;10000".format(out, index_name, index_value)
      index_name = index_name.replace('$', '')
      print("{0} load is {1}".format(index_name, index_value))
    #print out
    exit(code)

  def getLoadUser(self, hostname, domain, warn, crit):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)
    if s is None:
      print("UNKNOWN - {0} is not part of the citrix farm".format(MachineName))
      exit(3)

    if crit is None:
      crit = ''
    if warn is None:
      warn = ''

    if warn != '' and crit != '' and int(warn) > int(crit):
      print("UNKNOWN - Warning cannot be higher than Critical")
      exit(3)

    users = s['data']['AssociatedUserNames']
    userload = len(users)

    if crit != '' and userload > int(crit):
      status = 'CRITICAL'
      exit_code = 2
    elif warn != '' and userload > int(warn):
      status = 'WARNING'
      exit_code = 1
    else:
      status = 'OK'
      exit_code = 0
    print("{0} - Server has {1} users connected | load={1};{2};{3};;;".format(status, userload, warn, crit))
    for u in users:
      print(u)
    exit(exit_code)

  def getCatalogName(self, hostname, domain):
    MachineName = self.getMachineName(hostname, domain)
    s = self.data.get(MachineName)

    print("OK - {0}".format(s['data']['CatalogName']))

  def getDeliveryGroupLoadIndex(self, DesktopGroupName, warn, crit):
    if DesktopGroupName is None:
      print("UNKNOWN - DeliveryGroup name is necessary for this module")
      exit(3)

    if crit is None:
      crit = ''
    if warn is None:
      warn = ''

    if warn != '' and crit != '' and int(warn) > int(crit):
      print("UNKNOWN - Warning cannot be higher than Critical")
      exit(3)

    LoadIndex = 0
    TotalServers = 0
    MaintServers = 0
    UnregisteredServers = 0
    WaitingForReboot = 0
    AvailLoadIndex = 0
    for name in self.data.keys():
      s=self.data[name]
      if type(s) is not dict: continue
      if s['data']['DesktopGroupName'] == DesktopGroupName:
        LoadIndex += s['data']['LoadIndex']
        TotalServers += 1
        if s['data']['RegistrationState'] == 2 and s['data']['InMaintenanceMode'] is False:
          AvailLoadIndex += s['data']['LoadIndex']
        else:
          AvailLoadIndex += 10000
        if s['data']['RegistrationState'] != 2:
          UnregisteredServers += 1
        if s['data']['InMaintenanceMode']:
          MaintServers += 1
          for tag in s['data']['Tags']:
            if tag == 'RebootReady':
              WaitingForReboot += 1
    if TotalServers == 0:
      print('UNKNOWN - Servers in Delivery Group is 0. Maybe Delivery Group %s doesn\'t exist' % DesktopGroupName)
      exit(3)

    AverageLoad = int(LoadIndex / TotalServers)
    AvailLoadIndex = int(AvailLoadIndex / TotalServers)
    alert_message = ''
    if crit != '' and (AverageLoad > int(crit) or AvailLoadIndex > int(crit)):
      status = 'CRITICAL'
      alert_message = 'Delivery Group at max capacity({0}). '.format(AvailLoadIndex)
      exit_code = 2
    elif warn != '' and (AverageLoad > int(warn) or AvailLoadIndex > int(warn)):
      status = 'WARNING'
      alert_message = 'Delivery Group is reaching max capacity({0}). '.format(AvailLoadIndex)
      exit_code = 1
    else:
      status = 'OK'
      exit_code = 0

    print("{0} - Average DeliveryGroup load is {1}. | load={1};{2};{3};0;10000"
      .format(status, AvailLoadIndex, warn, crit))
    if exit_code != 0:
      print(alert_message)
      print('Check servers in Maintenance or Unregistered')
    print("Total Servers {0}".format(TotalServers))
    print("Maintenance Servers: {0}".format(MaintServers))
    print("Unregistered Servers: {0}".format(UnregisteredServers))
    print("Waiting for Reboot: {0}".format(WaitingForReboot))
    print("Available LoadIndex: {0}".format(AvailLoadIndex))
    exit(exit_code)

  def getDeliveryGroupLoadUser(self, DesktopGroupName, warn, crit):
    if DesktopGroupName is None:
      print("UNKNOWN - DeliveryGroup name is necessary for this module")
      exit(3)

    if crit is None:
      crit = ''
    if warn is None:
      warn = ''

    if warn != '' and crit != '' and int(warn) > int(crit):
      print("UNKNOWN - Warning cannot be higher than Critical")
      exit(3)

    LoadUser = 0
    for name in self.data.keys():
      s=self.data[name]
      if type(s) is not dict: continue
      if s['data']['DesktopGroupName'] == DesktopGroupName:
        LoadUser += len(s['data']['AssociatedUserSIDs'])

    if crit != '' and LoadUser > int(crit):
      status = 'CRITICAL'
      exit_code = 2
    elif warn != '' and LoadUser > int(warn):
      status = 'WARNING'
      exit_code = 1
    else:
      status = 'OK'
      exit_code = 0

    print("{0} - DeliveryGroup {1} users connected | load={1};{2};{3};;".format(status, LoadUser, warn, crit))

def auth_file(authfile):
  data = {}
  try:
    with open(authfile) as f:
      linenum = 0
      for l in f:
        linenum += 1
        #line = l.split("#")[0]
        line = l
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
    print "UNKNOWN - auth_file Error %s" % str(e)
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
  check_ctx_farm.py -D <ddc> -S <host domain name> -H <host name> < -d <user domain name> -u <username> -p <password> | -a <auth file> > [-r <refresh interval>] -m <module> -w <warning> -c <critical> -l
  check_ctx_farm.py -h

  <ddc> Citrix Desktop Deliver Controller hostname or IP address
  <host domain name> Session Host server domain name
  <host name> Session Host server to be queried
  <domain name> domain name the Session Host is a member of
  <username> UPN of the user in the domain with privileges in the Citrix Farm to collect data
  <password> password of the user with privileges in the Citrix Farm
  <auth file> file name containing user's credentials
  <refresh interval> Seconds to keep cache of the farm locally. default=600
  <module> Module to be queried
    rawData: Will print out raw data comming from the DDC about the hostname
    InMaintenance: will return the time the server has been in maintenance
      <warn> <crit>: minutes that the hostname has been in this state and that will generate an alert
    RegistrationState: will return the time the server has been in a specific state
      <warn> <crit>: minutes that the hostname has been in this state and that will generate an alert
    LoadIndex: will return the load index and the time it has been in this state
    LoadUser: will return the number of users connected
    DeliveryGroupLoadIndex: will return the average load of a delivery group
      -g <delivery group name>
    DeliveryGroupLoadUser: will return the number of users connected to a delivery group
      -g <delivery group name>
    CatalogName: will return the catalog name a server is part of.
      -l loads data from server. By default data is fetched from cache
"""
  print(usage)

def main():
  refresh_interval = 600
  ddc = None
  u_domain = None
  hostname = None
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
    opts, args = getopt.getopt(sys.argv[1:], "D:H:d:u:p:hm:w:c:g:a:S:r:l")

    for o, a in opts:
      if o == '-D':
        ddc = a
      elif o == '-H':
        hostname = a
      elif o == '-S':
        h_domain = a
      elif o == '-d':
        u_domain = a
      elif o == '-u':
        username = a
      elif o == '-p':
        password = a
      elif o == '-m':
        module = a
      elif o == '-w':
        warn = a
      elif o == '-c':
        crit = a
      elif o == '-g':
        DeliveryGroup = a
      elif o == '-a':
        authfile = a
      elif o == '-r':
        refresh_interval = int(a)
      elif o == '-l':
        load_from_server = True
      elif o == '-h':
        raise Exception("Unknown argument")

    if module is None and not load_from_server: raise Exception("Module is a mandatory argument")

    machines = CitrixXD(ddc, auth(username, u_domain, password, authfile), refresh_interval, load_from_server)

    if load_from_server:
      print("OK - Data loaded")
      exit(0)
    if module == 'rawData':
      machines.getRawData(hostname, h_domain)
    elif module == 'InMaintenance':
      machines.getInMaintenance(hostname, h_domain, warn, crit)
    elif module == 'RegistrationState':
      machines.getRegistrationState(hostname, h_domain, warn, crit)
    elif module == 'LoadIndex':
      machines.getLoadIndex(hostname, h_domain, warn, crit)
    elif module == 'LoadUser':
      machines.getLoadUser(hostname, h_domain, warn, crit)
    elif module == 'CatalogName':
      machines.getCatalogName(hostname, h_domain)
    elif module == 'DeliveryGroupLoadIndex':
      machines.getDeliveryGroupLoadIndex(DeliveryGroup, warn, crit)
    elif module == 'DeliveryGroupLoadUser':
      machines.getDeliveryGroupLoadUser(DeliveryGroup, warn, crit)
    else:
      raise Exception("Module not implemented")

  except Exception as err:
    print("UNKNOWN - main Error: %s" % str(err))
    usage()
    exit(3)

if __name__ == "__main__":
  main()
