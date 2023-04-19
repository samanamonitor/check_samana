#!/usr/bin/python3

from time import time
import traceback
from winrm.protocol import Protocol
from base64 import b64encode
import xml.etree.ElementTree as ET
from cgi import parse_qs, escape
import json
import sys, getopt
from samana.base import ping_host, perf, get_dns_ip, auth_file
from samana import nagios

def usage(message=""):
    if len(message) > 0:
        print(message)
    print("""Check WinRM v2.0.0
 This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
 SAMANA GROUP LLC. If you want to use it, you should contact us before
 to get a license.
 Copyright (c) 2019 Samana Group LLC

 Usage:
  %s [ -H <host name> ] [ -d <user domain name> -u <username> -p <password> | -a <auth file> ] [ -U <script URL> ] [ -A "<script arguments in quotes>"] [-w <warning>] [-c <critical>]

  <host name>        Windows server to be queried
  <domain name>      domain name the user
  <username>         SAMAccountName of the user
  <password>         password of the user
  <auth file>        file name containing user's credentials
  <script URL>       URL where Powershell script is located
""" % sys.argv[0])

class WinRMScript:
    def __init__(self, hostaddress, auth, cleanup=True, verbose=True):
        if auth is None:
            raise nagios.CheckUnknown("Authentication data missing")
        if 'domain' not in auth or auth['domain'] is None:
            raise nagios.CheckUnknown("The user domain name is a mandatory argument")
        if 'username' not in auth or auth['username'] is None:
            raise nagios.CheckUnknown("The username is a mandatory argument")
        if 'password' not in auth or auth['password'] is None:
            raise nagios.CheckUnknown("The password is a mandatory argument")

        self.cleanup = cleanup
        self.data = {}
        self.hostaddress = hostaddress
        self.verbose = verbose
        if 'upn' in auth:
            self.username = auth['username']
        else:
            self.username = auth['domain'] + '\\' + auth['username']
        self.password = auth['password']

    def run(self, scripturl, scriptarguments, warning, critical):
        scriptpath = "c:\\samanamon"
        scriptname = scripturl.split('/')[-1]
        variables= { 
            'scripturl': scripturl, 
            'scriptpath': scriptpath, 
            'scriptname': scriptname,
            'scriptarguments': scriptarguments,
            'cleanup': "$%s" % (str(self.cleanup)),
            'warning': " -Warning %d" % warning if warning >= 0 else "",
            'critical': " -Critical %d" % critical if critical >= 0 else ""
            }
        script = '''$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference="Stop"
$VerbosePreference = "Continue"
$ScriptPath="%(scriptpath)s"
$ScriptName="%(scriptname)s"
$ScriptArgs="%(scriptarguments)s"
$ScriptURL="%(scripturl)s"
$CleanUp=%(cleanup)s
if (-Not (Test-Path $ScriptPath)) { 
    mkdir $ScriptPath | Out-Null
    "Folder created." | Write-Verbose
}
if (-Not (Test-Path $ScriptPath\\$ScriptName) -Or $CleanUp) {
    Invoke-WebRequest -Uri $ScriptURL -OutFile "$ScriptPath\\$ScriptName"
    if (-Not (Test-Path $ScriptPath\\$ScriptName)) { 
        "File not downloaded" | Write-Error; 
        exit 3
    }
    "Script Downloaded." | Write-Verbose
}
$cmd = Join-Path -Path $ScriptPath -ChildPath $ScriptName
Invoke-Expression "$cmd $ScriptArgs%(warning)s%(critical)s"

$ret=$LASTEXITCODE
"Done executing script" | Write-Verbose
if ($CleanUp -eq $True) {
    Remove-Item -Recurse -Force $ScriptPath
    "Done cleanup" | Write-Verbose
}
exit $ret''' % variables
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
            command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand',  encoded_ps ])
            std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
            self.check_error(std_err.decode('ascii'))

        except nagios.CheckUnknown:
            raise
        except Exception as e:
            raise nagios.CheckUnknown("***There was an error executing the script on the server(%s)" % type(e).__name__, 
                addl=str(e).strip())
        finally:
            p.cleanup_command(shell_id, command_id)
            p.close_shell(shell_id)

        if status_code == 2:
            raise nagios.CheckCritical(std_out.decode('ascii').strip(), addl=self.get_verbose(std_err.decode('ascii')))
        if status_code == 1:
            raise nagios.CheckWarning(std_out.decode('ascii').strip(), addl=self.get_verbose(std_err.decode('ascii')))

        return nagios.CheckResult(std_out.decode('ascii').strip(), addl=self.get_verbose(std_err.decode('ascii')))

    def get_verbose(self, std_err):
        if not self.verbose: return ""
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
        msg="Verbose Data:\n"
        for tag in root.findall('./ps:S[@S="verbose"]', ns):
            msg += tag.text + "\n"
        return msg

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
        for tag in root.findall('./ps:S[@S="Error"]', ns):
            error = True
            msg += "Error : %s\n" % tag.text.replace("_x000D__x000A_", "")
        if error:
            raise nagios.CheckUnknown(msg)

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

def process_data(hostaddress=None, url=None, username=None, 
        password=None, u_domain=None, authfile=None, 
        warning=-1, critical=-1, scriptarguments='', verbose=False, cleanup=True):
    status = 3
    out = ''
    addl = ''
    perf_data = []
    winrm_time = 0
    try:
        if hostaddress is None:
            raise nagios.CheckUnknown("Invalid Host address")

        if url is None:
            raise nagios.CheckUnknown("Powershell script location not defined.")

        user_auth = auth(username, u_domain, password, authfile)
        if user_auth is None:
            raise nagios.CheckUnknown("Invalid authentication information")

        if warning != -1:
            try:
                warning = int(warning)
            except ValueError:
                raise nagios.CheckUnknown("Invalid Warning values")

        if critical != -1:
            try:
                critical = int(critical)
            except ValueError:
                raise nagios.CheckUnknown("Invalid Critical values")

        (hostip, dns_time) = get_dns_ip(hostaddress)
        perf_data += [ "dns_resolution=%d;;;;" % dns_time ]
        ping_data = ping_host(hostip)
        perf_data += [ "ping_rtt=%d;;;;" % ping_data['avg'] ]
        perc_packet_loss = 100-int(100.0 * ping_data['packets_received'] / ping_data['packets_sent'])
        perf_data += [ "ping_perc_packet_loss=%d;;;;" % perc_packet_loss ]


    except nagios.CheckException as e:
        return e.result

    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        return nagios.CheckResult("%s at %s\n%s" % (e, tb.tb_lineno, traceback_info), 
            addl=addl, status=3, status_str='UNKNOWN')

    try:
        winrm_start = time()
        client = WinRMScript(hostaddress, user_auth, verbose=verbose, cleanup=cleanup)
        response_data = client.run(url, scriptarguments, warning, critical)
    except nagios.CheckException as e:
        response_data = e.result
    finally:
        winrm_time = (time() - winrm_start) * 1000
        perf_data += [ "winrm_time=%d;;;;" % winrm_time ]

    response_data.perf_data = perf_data
    return response_data

def application (environ, start_response):
    data = {
        'hostaddress': None,
        'u_domain': None,
        'username': None,
        'password': None,
        'authfile': None,
        'nagiosaddress': None,
        'script': None,
        'warning': -1,
        'critical': -1,
        'url': None,
        'scriptarguments': None,
        'cleanup': True
    }

    d = parse_qs(environ['QUERY_STRING'])
    for k in data.keys():
        data[k] = d.get(k, [ None ])[0]
    response_body = json.dumps(process_data(**data))

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

def main():
    hostaddress = None
    u_domain = None
    username = None
    password = None
    authfile = None
    nagiosaddress = None
    script = None
    warning = -1
    critical = -1
    url = None
    scriptarguments = None
    cleanup = True
    verbose = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:n:s:w:c:U:A:Cv")
    except Exception as e:
        usage("UNKNOWN - Invalid parameter")
        exit(3)

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
            try:
                warning = int(a)
            except ValueError:
                print("UNKNOWN - Invalid value for warning")
                exit(3)
        elif o == '-c':
            try:
                critical = int(a)
            except ValueError:
                print("UNKNOWN - Invalid value for critical")
                exit(3)
        elif o == '-U':
            url = a
        elif o == '-A':
            scriptarguments = a
        elif o == '-C':
            cleanup = False
        elif o == '-v':
            verbose = True
        else:
            usage()
            exit(3)

    response_data = process_data(hostaddress=hostaddress, url=url, username=username, 
        password=password, u_domain=u_domain, authfile=authfile, 
        warning=warning, critical=critical, scriptarguments=scriptarguments, verbose=verbose, cleanup=cleanup)

    print(response_data)
    exit(response_data.status)

if __name__ == "__main__":
  main()
