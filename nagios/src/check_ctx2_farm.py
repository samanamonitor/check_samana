#!/usr/bin/python

import json
import sys, getopt
import time
import unicodedata
import urllib3

TYPE_FARM        = 0
TYPE_DESKTOPGROUP= 1
TYPE_SERVER      = 2

STATUS_OK        = 0
STATUS_WARNING   = 1
STATUS_CRITICAL  = 2
STATUS_UNKNOWN   = 3

STATUS = [
  'OK',
  'WARNING',
  'CRITICAL',
  'UNKNOWN'
  ]

REGISTRATION_STATE = [
  'Unregistered', 
  'Initializing', 
  'Registered', 
  'AgentError'
]

REGISTRATION_STATENUM = {
  'Unregistered': 0, 
  'Initializing': 1, 
  'Registered': 2, 
  'AgentError': 3
}

class CXDToolOld(Exception):
  pass

class CXDNotFound(Exception):
  pass

class CXDInvalidData(Exception):
  pass

class CitrixXD:
  def __init__(self, ddc=None, hostname=None, deliverygroup=None, etcdserver="127.0.0.1", etcdport="2379"):
    if ddc is None:
      raise Exception("The DDC is a mandatory argument")

    self.data = {}
    self.ddc = ddc
    path = "/v2/keys/samanamonitor/ctx_data/%s" % ddc
    if hostname is not None:
      path += "/hosts/" + hostname
      self.type = TYPE_SERVER
    elif deliverygroup is not None:
      path += "/desktopgroup/" + deliverygroup
      self.type = TYPE_DESKTOPGROUP
    else:
      path += "/farm"
      self.type = TYPE_FARM

    try:
      http = urllib3.PoolManager()
      r = http.request('GET', 'http://%s:%s/%s' % (etcdserver, etcdport, path))
      if r.status != 200: raise KeyError
      self.data =json.loads(json.loads(r.data.decode('UTF-8'))['node']['value'])
      if 'epoch' not in self.data: raise ValueError
      age_secs = time.time() - self.data['epoch']
      if age_secs > 600:
        raise CXDToolOld("Data is too old %d seconds" % age_secs)
    except KeyError:
      if hostname is not None:
        raise CXDNotFound("Server \"%s\" not found in the database" % hostname)
      if deliverygroup is not None:
        raise CXDNotFound("Delivery Group \"%s\" not found in the database" % deliverygroup)
    except ValueError:
      if hostname is not None:
        raise CXDInvalidData("Data for Server \"%s\" is corrupt" % hostname)
      if deliverygroup is not None:
        raise CXDInvalidData("Data for Server \"%s\" is corrupt" % deliverygroup)

  def getRawData(self):
    addl_data="Last push: %d s\n" % (time.time() - self.data['epoch'])
    addl_data += json.dumps(self.data)
    return (
      0,
      "Data Follows",
      addl_data,
      None, # data min
      None  # data max
      )

  def getLoadIndex(self):
    addl_data="Last push: %d s\n" % (time.time() - self.data['epoch'])
    if self.type == TYPE_FARM or self.type == TYPE_DESKTOPGROUP:
      addl_data += "%s\n%s\n%s" % (
        "Total Servers: %d" % self.data['TotalServers'],
        "Maintenance Servers: %d" % self.data['InMaintenanceMode'],
        "Registered Servers: %d" % self.data['Registered'],
        )
    return (
      int(self.data['LoadIndex']),
      "Load is %d" % int(self.data['LoadIndex']),
      addl_data,
      0,
      10000,
      "load"
      )

  def getLoadUser(self):
    addl_data="Last push: %d s\n" % (time.time() - self.data['epoch'])
    return (
      int(self.data['SessionCount']),
      "Users connected %d" % int(self.data['SessionCount']),
      addl_data,
      None,
      None,
      "load"
      )

  def getInMaintenance(self):
    addl_data="Last push: %d s\n" % (time.time() - self.data['epoch'])
    if self.type != TYPE_SERVER:
      raise CXDInvalidData("This information can only be obtained from a host")
    return (
      str(self.data['InMaintenanceMode']).lower(),
      "Server %s in Maintenance Mode (%s)" % (
        "IS" if self.data['InMaintenanceMode'] else "IS NOT", 
        str(self.data['InMaintenanceMode']).lower()),
      addl_data,
      None,
      None,
      None
      )

  def getRegistrationState(self):
    addl_data="Last push: %d s\n" % (time.time() - self.data['epoch'])
    if self.type != TYPE_SERVER:
      raise CXDInvalidData("This information can only be obtained from a host")

    if isinstance(self.data['RegistrationState'], int):
      registrationstate_str = REGISTRATION_STATE[self.data['RegistrationState']]
      registrationstate_num = self.data['RegistrationState']
    else:
      registrationstate_str = self.data['RegistrationState']
      registrationstate_num = REGISTRATION_STATENUM[self.data['RegistrationState']]

    return (
      registrationstate_str,
      "Server registration state is %s (%s)" % (
        registrationstate_str, 
        registrationstate_num),
      addl_data,
      None,
      None,
      None
      )

  def getDesktopGroupName(self):
    addl_data="Last push: %d s\n" % (time.time() - self.data['epoch'])
    if self.type != TYPE_SERVER:
      raise CXDInvalidData("This information can only be obtained from a host")
    return (
      self.data['DesktopGroupName'].lower(),
      "Server is in \"%s\" Delivery Group" % self.data['DesktopGroupName'],
      addl_data,
      None,
      None,
      None
      )

def nagios_output(output, warning=None, critical=None, expected_text=None, perfmin=None, perfmax=None):
  if expected_text is not None:
    if str(output[0]) == str(expected_text) or expected_text == '':
      print "OK - %s" % output[1]
      print output[2]
      return 0
    else:
      print "CRITICAL - %s" % output[1]
      print output[2]
      return 2

  try:
    critical = int(critical)
    str_critical = str(critical)
  except:
    critical = None
    str_critical = ''

  try:
    warning = int(warning)
    str_warning = str(warning)
  except:
    warning = None
    str_warning = ''

  perfmin = '' if output[3] is None else output[3]
  perfmax = '' if output[4] is None else output[4]

  perfdata = "%s=%d;%s;%s;%s;%s" % (output[5], output[0], str_warning, str_critical, perfmin, perfmax)
  if critical is not None and output[0] > critical:
    status = STATUS_CRITICAL
  elif warning is not None and output[0] > warning:
    status = STATUS_WARNING
  else:
    status = STATUS_OK

  print "%s - %s | %s" % (STATUS[status], output[1], perfdata)
  print output[2]
  return status



def usage():
  usage = """Check Citrix DDC v2.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2017 Samana Group LLC

Usage:
  check_ctx2_farm.py -D <ddc> [ -e <etcdserver[:port]> ] -m <module> -w <warning> -c <critical> [ [-H <host name>] | [-g <delivery group name>] ]
  check_ctx2_farm.py -h

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
    DeliveryGroupName: will return the Delivery Group name a server is part of.
"""
  print(usage)

def main():
  ddc = None
  hostname = None
  module = None
  warn = None
  crit = None
  deliverygroup = None
  expected_text = None
  etcdserver = "127.0.0.1"
  etcdport = "2379"
  try:
    opts, args = getopt.getopt(sys.argv[1:], "D:H:hm:w:c:g:x:e:")

    for o, a in opts:
      if o == '-D':
        ddc = a.lower()
      elif o == '-H':
        hostname = a.lower()
      elif o == '-m':
        module = a.lower()
      elif o == '-w':
        try:
          warn = int(a)
        except:
          warn = None
      elif o == '-c':
        try:
          crit = int(a)
        except:
          crit = None
      elif o == '-g':
        deliverygroup = a.lower()
      elif o == '-x':
        expected_text = a
      elif o == '-e':
        temp = a.split(':')
        etcdserver = temp[0]
        if len(temp) > 1:
          etcdport = temp[1]
      elif o == '-h':
        raise Exception("Unknown argument")

    if module is None: 
      raise Exception("Module is a mandatory argument")

    machines = CitrixXD(ddc=ddc, hostname=hostname, deliverygroup=deliverygroup, etcdserver=etcdserver, etcdport=etcdport)

    if module == 'rawdata':
      output = machines.getRawData()
      if expected_text is None: expected_text = ''
    elif module == 'inmaintenance':
      output = machines.getInMaintenance()
      if expected_text is None: expected_text = ''
    elif module == 'registrationstate':
      output = machines.getRegistrationState()
      if expected_text is None: expected_text = ''
    elif module == 'deliverygroupname':
      output = machines.getDesktopGroupName()
      if expected_text is None: expected_text = ''
    elif module == 'loadindex':
      output = machines.getLoadIndex()
    elif module == 'loaduser':
      output = machines.getLoadUser()
    else:
      raise Exception("Module not implemented")

  except getopt.GetoptError as err:
    print "UNKNOWN - Invalid parameter: %s" % str(err)
    usage()
    exit(3)
  except Exception as err:
    print "UNKNOWN - %s" % str(err)
    usage()
    exit(3)

  exit(nagios_output(output, warn, crit, expected_text))

if __name__ == "__main__":
  main()
