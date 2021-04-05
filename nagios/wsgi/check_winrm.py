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


def application ( environ, start_response):

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

        response_body = 'Request method: %s \n%s' % (environ['REQUEST_METHOD'], data)


        status = '200 OK'
        response_headers = [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(response_body)))
        ]

    except Exception as e:
        status = "400 Bad Request"
        msg = "UNKNOWN"
        response_body = "Error: %s" % e
        response_headers = [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(response_body)))
        ]



    start_response(status, response_headers)

    return [response_body]