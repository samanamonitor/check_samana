#!/usr/bin/python

from winrm.protocol import Protocol
from base64 import b64encode
import json
import sys, getopt
import time
import random
import unicodedata

class ScheduledTask:
  def __init__(self, hostname, auth):
    if 'upn' in auth:
      self.username = auth['username']
    else:
      self.username = auth['domain'] + '\\' + auth['username']
    self.password = auth['password']
    self.hostname = hostname
    
  def getLastTaskResult(self, taskname):
    script = """
$task = Get-ScheduledTaskInfo -TaskName %s
$task.LastTaskResult
""" % taskname

    shell_id = None
    command_id = None
    p = None
    error = False
    try:
      p = Protocol(
        endpoint='https://' + self.hostname + ':5986/wsman',
        transport='ntlm',
        username=self.username,
        password=self.password,
        server_cert_validation='ignore')
      shell_id = p.open_shell()
      encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
      command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand {0}'.format(encoded_ps), ])
      std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
      lasttaskresult = std_out.rstrip()
    except Exception as e:
      print("UNKNOWN - Unable to get data from server (%s) %s." % (str(e), type(e).__name__))
      error = True
    finally:
      p.cleanup_command(shell_id, command_id)
      p.close_shell(shell_id)
    if error: exit(3)
    return lasttaskresult

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
  usage = """Check TaskScheduler v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2017 Samana Group LLC

Usage:
  check_task_sched.py -H <host name> < -d <user domain name> -u <username> -p <password> | -a <auth file> > -t <task name> -e <expected result>
  check_citrixddc -h

  <host name> Session Host server to be queried
  <domain name> domain name the Session Host is a member of
  <username> UPN of the user in the domain with privileges in the Citrix Farm to collect data
  <password> password of the user with privileges in the Citrix Farm
  <auth file> file name containing user's credentials
  <task name> Windows Server task name
  <expected result> Expected result of last execution of task
"""
  print(usage)

def main():
  u_domain = None
  hostname = None
  h_domain = None
  username = None
  password = None
  taskname = None
  expected = None
  authfile = None
  try:
    opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:t:e:")

    for o, a in opts:
      if o == '-H':
        hostname = a
      elif o == '-d':
        u_domain = a
      elif o == '-u':
        username = a
      elif o == '-p':
        password = a
      elif o == '-a':
        authfile = a
      elif o == '-t':
        taskname = a
      elif o == '-e':
        expected = a
      elif o == '-h':
        raise Exception("Unknown argument")
        
    if taskname is None or taskname == '':
      raise Exception("Invalid task name")
    if hostname is None or hostname == '':
      raise Exception("Invalid hostname")

    task = ScheduledTask(hostname, auth(username, u_domain, password, authfile))
    current_value = task.getLastTaskResult(taskname)
    if current_value == expected:
      print "OK - Task %s is responding" % taskname
      exit(0)
    else:
      print "CRITICAL - Task %s is not responding. Last result = %s" % (taskname, current_value)
      exit(2)

  except Exception as err:
    print "UNKNOWN - main Error: " + str(err)
    usage()
    exit(3)

if __name__ == "__main__":
  main()
