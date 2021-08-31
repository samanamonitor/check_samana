from winrm.protocol import Protocol
from base64 import b64encode
import xml.etree.ElementTree as ET

class WinRMScript:
  def __init__(self, hostaddress, auth, cleanup=True):
    try:
      if auth is None:
        raise Exception("Authentication data missing")
      if 'domain' not in auth or auth['domain'] is None:
        raise Exception("The user domain name is a mandatory argument")
      if 'username' not in auth or auth['username'] is None:
        raise Exception("The username is a mandatory argument")
      if 'password' not in auth or auth['password'] is None:
        raise Exception("The password is a mandatory argument")

      self.cleanup = cleanup
    except Exception as e:
      print("UNKNOWN - Error %s" % str(e))
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
"Done cleanup" | Out-Host
''' % { 'scripturl': scripturl, 
      'scriptpath': scriptpath, 
      'scriptname': scriptname,
      'scriptarguments': scriptarguments,
      'hostaddress': self.hostaddress
      }
    else:
      script = '''
%(scriptpath)s\\%(scriptname)s %(scriptarguments)s| Out-Host
"Done executing script" | Out-Host
''' % {
      'scriptpath': scriptpath, 
      'scriptname': scriptname,
      'scriptarguments': scriptarguments,
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
      self.check_error(std_err)
      if status_code != 0:
        print("ERROR - %s" % std_err)
        error = 1
    except Exception as e:
      print("UNKNOWN - Unable to get data from Server (%s)\n%s." % (type(e).__name__, str(e)))
      error = 3
    finally:
      p.cleanup_command(shell_id, command_id)
      p.close_shell(shell_id)
    if error > 0: exit(error)
    return "%s\n%s" % (std_out, "")

  def check_error(self, std_err):
    if len(std_err) == 0:
      return
    if std_err[0] == '#':
      temp = std_err.split('\n', 1)
      if len(temp) > 0:
        std_err = temp[1]
    root = ET.fromstring(std_err)
    ns={ 'ps':root.tag.split('}')[0].split('{')[1] }
    msg = ""
    error = False
    for tag in root.findall('./ps:S', ns):
      t = tag.get('S')
      if t == 'Error':
        error = True
      msg += "%s : %s\n" % (t, tag.text)
    if error:
      raise Exception(msg)