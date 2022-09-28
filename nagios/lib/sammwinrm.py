from winrm.protocol import Protocol
from base64 import b64encode
import xml.etree.ElementTree as ET
from time import time
import os

import xmltodict
import base64
import uuid


class WRProtocol(Protocol):
    namespace = {
        'a': "http://schemas.xmlsoap.org/ws/2004/08/addressing",
        's': "http://www.w3.org/2003/05/soap-envelope",
        'w': "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd",
        'rsp': "http://schemas.microsoft.com/wbem/wsman/1/windows/shell",
        'p': "http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd"
    }
    def get(self, shell_id):
        message_id = uuid.uuid4()
        req = {
            'env:Envelope': self._get_soap_header(
            resource_uri='http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_ComputerSystem',  # NOQA
            action='http://schemas.xmlsoap.org/ws/2004/09/transfer/Get')}
        #req['env:Envelope']['env:Header']['w:SelectorSet'] = {
        #    'w:Selector': { '@Name': 'id', '#text': '1'}
        #    }
        req['env:Envelope'].setdefault('env:Body', {})
        print(xmltodict.unparse(req))
        res=self.send_message(xmltodict.unparse(req))
        return res

    def signal(self, shell_id, command_id, s):
        message_id = uuid.uuid4()
        req = {'env:Envelope': self._get_soap_header(
            resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
            action='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Signal',  # NOQA
            shell_id=shell_id,
            message_id=message_id)}

        # Signal the Command references to terminate (close stdout/stderr)
        signal = req['env:Envelope'].setdefault(
            'env:Body', {}).setdefault('rsp:Signal', {})
        signal['@CommandId'] = command_id
        signal['rsp:Code'] = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/signal/%s' % s  # NOQA

        res = self.send_message(xmltodict.unparse(req))        
        return res

    def send(self, shell_id, command_id, stdin_input, end=False):
        req = {'env:Envelope': self._get_soap_header(
                    resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
                    action='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Send',  # NOQA
                    shell_id=shell_id)}
        stdin_envelope = req['env:Envelope'].setdefault('env:Body', {}).setdefault(
                    'rsp:Send', {}).setdefault('rsp:Stream', {})
        stdin_envelope['@CommandId'] = command_id
        stdin_envelope['@Name'] = 'stdin'
        stdin_envelope['@End'] = str(end)
        stdin_envelope['@xmlns:rsp'] = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell'
        stdin_envelope['#text'] = base64.b64encode(stdin_input)
        start_time = time()
        res = self.send_message(xmltodict.unparse(req))
        total_time = time() - start_time
        return (res, total_time)

    def receive(self, shell_id, command_id):
        req = {'env:Envelope': self._get_soap_header(
                    resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
                    action='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive',  # NOQA
                    shell_id=shell_id)}
        stream = req['env:Envelope'].setdefault('env:Body', {}).setdefault(
            'rsp:Receive', {}).setdefault('rsp:DesiredStream', {})
        stream['@CommandId'] = command_id
        stream['#text'] = 'stdout stderr'
        start_time = time()
        res = self.send_message(xmltodict.unparse(req))
        total_time = time() - start_time
        root = ET.fromstring(res)

        stdout = stderr = b''
        stream_stdout = root.findall('.//rsp:Stream[@Name=\'stdout\']', self.namespace)
        for stream_node in stream_stdout:
            if stream_node.text is not None:
                stdout += base64.b64decode(stream_node.text.encode('ascii'))
        stream_stderr = root.findall('.//rsp:Stream[@Name=\'stderr\']', self.namespace)
        for stream_node in stream_stderr:
            if stream_node.text is not None:
                stderr += base64.b64decode(stream_node.text.encode('ascii'))

        cs=root.find('.//rsp:CommandState[@State=\'%(rsp)s/CommandState/Done\']' % self.namespace, self.namespace)
        command_done = cs is not None
        ec=root.find('.//rsp:ExitCode', self.namespace)
        if ec is not None:
            return_code = int(ec.text)
        else:
            return_code = -1
        return stdout, stderr, return_code, command_done, total_time

class WinRMCommand:
    def __init__(self, shell):
        self.shell = shell
        self.data={}
        self.command_id = None
        self.std_out = None
        self.std_err = None
        self.code = None
        self.done = None
        self.total_time = None
        self.error = False

    def signal(self, s):
        self.signal_res = self.shell.signal(self.command_id, s)

    def close(self):
        if self.command_id is not None:
            command_id=self.command_id
            self.signal('terminate')
            self.command_id = None

    def send(self, command, expect_receive=True, end=False):
        if not self.interactive:
            return
        self.send_data = self.shell.send(command, self.interactive, expect_receive=expect_receive, end=end)

    def receive(self):
        if self.command_id is None:
            return None
        self.std_out, self.std_err, self.code, self.done, self.total_time = \
            self.shell.receive(self.command_id, self.interactive)

        return self.shell.receive(self.command_id, self.interactive)

    def exit(self):
        self.send_data = self.shell.send(self.command_id, 'exit\r\n', end=True)


class WMICommand(WinRMCommand):
    def __init__(self, shell, class_name=None, class_filter=None):
        WinRMCommand.__init__(self, shell)
        self.class_name = class_name
        self.class_filter = class_filter
        self.interactive = self.class_name is not None

    def run(self):
        params = []
        if self.class_name is not None:
            params += [ 'PATH', self.class_name ]
            if self.class_filter is not None:
                params += [ 'WHERE', self.class_filter ]
            params += [ 'GET', '/FORMAT:RAWXML' ]
        self.command_id = self.shell.run_command('wmic', params)
        WinRMCommand.receive(self)
        if self.class_name is not None:
            self.process_result()

    def process_result(self):
        try:
            self.root = ET.fromstringlist(self.std_out.replace('\r','').split('\n')[:-1])
        except Exception as e:
            return
        for property in self.root.findall(".//PROPERTY"):
            n=property.attrib['NAME']
            v=property.find("./VALUE")
            self.data[n]=v.text if v is not None else None


    def get_class(self, class_name, class_filter=None):
        cmd="PATH %s" % class_name
        if class_filter is not None:
            cmd += " WHERE " + class_filter
        res=self.send(cmd + " GET /format:rawxml")
        return res

    def __str__(self):
        return self.command_id
    def __repr__(self):
        return "<%s interactive=%s%s%s error=%s std_out_bytes=%d std_err_bytes=%d>" % \
            (self.__class__.__name__, self.interactive,
                " class_name=%s" % self.class_name if self.class_name is not None else "",
                " class_filter=%s" % self.class_filter if self.class_filter is not None else "",
                self.error,
                len(self.std_out), len(self.std_err))

class WinRMShellNotConnected(Exception):
    pass

class WinRMShell:
    def __init__(self, cleanup=True):
        self.cleanup = cleanup
        self.data = {}
        self.shell_id = None
        self.command_id = None
        self.connected = False
        self.username = None
        self.password = None
        self.domain = None
        self.hostaddress = None
        self.transport = 'ntlm'
        self.wrport=5985
        self.wrprotocol='http'

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.close()

    def open(self, hostaddress=None, auth=None):
        self.username = os.environ.get('WINRM_USER')
        self.password = os.environ.get('WINRM_PASSWORD')
        self.domain = os.environ.get('WINRM_DOMAIN')
        self.hostaddress = os.environ.get('WINRM_HOSTNAME')
        if auth is not None:
            self.username = auth.get('username')
            self.password = auth.get('password')
            self.domain = auth.get('domain')

        if self.username is None:
            raise Exception("The username is a mandatory argument")
        if self.password is None:
            raise Exception("The password is a mandatory argument")
        if self.domain is None:
            raise Exception("The user domain name is a mandatory argument")

        if hostaddress is not None:
            self.hostaddress = hostaddress

        self.p = WRProtocol(
            endpoint='%s://%s:%d/wsman' % (self.wrprotocol, self.hostaddress, self.wrport),
            transport=self.transport,
            username=self.username,
            password=self.password)
        self.shell_id = self.p.open_shell()
        self.connected = True

    def run_command(self, cmd, params=[]):
        if not self.connected:
            raise WinRMShellNotConnected()
        return self.p.run_command(self.shell_id, cmd, params)

    def __str__(self):
        return self.shell_id

    def __repr__(self):
        return "<%s connected=%s hostaddress=%s username=%s domain=%s shell_id=%s>" % \
            ("WinRMShell", self.connected, self.hostaddress, \
                self.username, self.domain, self.shell_id)

    def close(self):
        if not self.connected:
            raise WinRMShellNotConnected()
        self.p.close_shell(self.shell_id)
        self.shell_id = None
        self.connected = False

    def signal(self, command_id, s):
        if not self.connected:
            raise WinRMShellNotConnected()
        return self.p.signal(self.shell_id, command_id, s)

    def send(self, command, expect_receive=True, end=False):
        if not self.connected:
            raise WinRMShellNotConnected()
        self.send_res = self.p.send(self.shell_id, self.command_id, command + "\r\n", end)
        if expect_receive:
            return self.p.receive(self.shell_id, self.command_id)
        else:
            return None

    def receive(self, command_id, interactive=False):
        if not self.connected:
            raise WinRMShellNotConnected()
        stdin_data = ''
        stderr_data = ''
        total_time = 0
        while True:
            res=self.p.receive(self.shell_id, command_id)
            if interactive and res[3] == False:
                return res
            stdin_data += res[0]
            stderr_data += res[1]
            total_time += res[4]
            if res[3] == True:
                break
        return (stdin_data, stderr_data, res[2], res[3], total_time)

    def urlfile(self, url, remotefile):
        cmd="(new-object System.Net.WebClient).DownloadFile(\"%s\", \"%s\")" \
            % (url, remotefile)
        return self.posh(scriptline=cmd)

    def getfile(self, remotefile):
        self.command_id = self.p.run_command(self.shell_id, 'type', [ remotefile ])
        return self.receive()

    def cmd(self, params=[], interactive=False):
        if len(params) == 0:
            interactive = True
        self.command_id = self.p.run_command(self.shell_id, params[0], params[1:])
        res=self.receive(interactive)
        return res

    def posh(self, scriptline=None, scriptfile=None):
        script = None
        if scriptfile is not None:
            with open(scriptfile, "r") as f:
                script = "$ProgressPreference = \"SilentlyContinue\";" + f.read()
        elif scriptline is not None:
            script = "$ProgressPreference = \"SilentlyContinue\";" + scriptline
        if script is not None:
            interactive = False
            encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
            params = [ '-encodedcommand', encoded_ps ]
        else:
            interactive = True
            params = []

        self.command_id = self.p.run_command(self.shell_id, 'powershell', params)
        res=self.receive(interactive)
        err = self.decode_posh_error(res[1])
        res += (err,)
        return res

    def decode_posh_error(self, std_err):
        if len(std_err) == 0:
            return std_err
        if std_err[0] == '#':
            temp = std_err.split('\n', 1)
            if len(temp) > 0:
                std_err = temp[1]
        try:
            root = ET.fromstring(std_err)
        except ET.ParseError:
            return std_err
        ns={ 'ps':root.tag.split('}')[0].split('{')[1] }
        msg = ""
        error = False
        for tag in root.findall('./ps:S', ns):
            t = tag.get('S')
            if t == 'Error':
                error = True
            msg += "%s : %s" % (t, tag.text.replace("_x000D__x000A_", "\n"))
        if error:
            msg = "Error executing Powershell Command.\n" + msg
        return msg

