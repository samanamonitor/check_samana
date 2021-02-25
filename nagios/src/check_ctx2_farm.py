#!/usr/bin/python

import json
import sys, getopt
import time
import unicodedata
import urllib3

class CXDToolOld(Exception):
  pass

class CXDNotFound(Exception):
  pass

class CXDInvalidData(Exception):
  pass

class CitrixXD:
  def __init__(self, ddc=None, hostname=None, deliverygroup=None):
    if ddc is None:
      raise Exception("The DDC is a mandatory argument")

    self.data = {}
    self.ddc = ddc
    path = "/samanamonitor/ctx_data/%s" % ddc
    if hostname is not None:
      path += "/hosts/" + hostname
    elif deliverygroup is not None:
      path += "/deliverygroup/" + deliverygroup
    else:
      path += "/farm"

    try:
      http = urllib3.PoolManager()
      r = http.requst('GET', 'http://localhost:2379' + path)
      self.data =json.loads(r.data)
      age_secs = time.time() - self.data['epoch']
      if age_secs > 600:
        raise CXDToolOld("UNKNOWN - Data is too old %d seconds" % age_secs)
    except etcd.EtcdKeyNotFound:
      if hostname is not None:
        raise CXDNotFound("UNKNOWN - Server \"%s\" not found in the database" % hostname)
      if deliverygroup is not None:
        raise CXDNotFound("UNKNOWN - Delivery Group \"%s\" not found in the database" % deliverygroup)
    except ValueError:
      if hostname is not None:
        raise CXDInvalidData("UNKNOWN - Data for Server \"%s\" is corrupt" % hostname)
      if deliverygroup is not None:
        raise CXDInvalidData("UNKNOWN - Data for Server \"%s\" is corrupt" % deliverygroup)

  def getRawData(self):
    print(json.dumps(self.data))
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
      index_name = unicodedata.normalize('NFKD', index_name).encode('ascii', 'ignore').translate(None, '$')
      #out = "{0} '{1}'={2};;;0;10000".format(out, index_name, index_value)
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
      print u
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
    for name, s in self.data.iteritems():
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
      print 'UNKNOWN - Servers in Delivery Group is 0. Maybe Delivery Group %s doesn\'t exist' % DesktopGroupName
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
    for name, s in self.data.iteritems():
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
  usage = """Check Citrix DDC v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2017 Samana Group LLC

Usage:
  check_ctx_farm.py -D <ddc> -m <module> -w <warning> -c <critical> [ [-H <host name>] | [-g <delivery group name>] ]
  check_ctx_farm.py -h

  <ddc> Citrix Desktop Deliver Controller hostname or IP address
  <host name> Session Host server to be queried
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
  ddc = None
  hostname = None
  module = None
  warn = None
  crit = None
  deliverygroup = None
  try:
    opts, args = getopt.getopt(sys.argv[1:], "D:H:hm:w:c:g:")

    for o, a in opts:
      if o == '-D':
        ddc = a
      elif o == '-H':
        hostname = a
      elif o == '-m':
        module = a
      elif o == '-w':
        warn = a
      elif o == '-c':
        crit = a
      elif o == '-g':
        deliverygroup = a
      elif o == '-h':
        raise Exception("Unknown argument")

    if module is None: 
      raise Exception("Module is a mandatory argument")

    machines = CitrixXD(ddc=ddc, hostname=hostname, deliverygroup=deliverygroup)

    if module == 'rawData':
      machines.getRawData()
    elif module == 'InMaintenance':
      machines.getInMaintenance()
    elif module == 'RegistrationState':
      machines.getRegistrationState()
    elif module == 'LoadIndex':
      machines.getLoadIndex()
    elif module == 'LoadUser':
      machines.getLoadUser()
    elif module == 'CatalogName':
      machines.getCatalogName()
    elif module == 'DeliveryGroupLoadIndex':
      machines.getDeliveryGroupLoadIndex()
    elif module == 'DeliveryGroupLoadUser':
      machines.getDeliveryGroupLoadUser()
    else:
      raise Exception("Module not implemented")

  except getopt.GetoptError as err:
    print "Invalid parameter: %s" % str(err)
    usage()
    exit(3)
  except Exception as err:
    print "UNKNOWN - main Error: " + str(err)
    usage()
    exit(3)

if __name__ == "__main__":
  main()
