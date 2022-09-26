from winrm.protocol import Protocol
from base64 import b64encode
import xml.etree.ElementTree as ET
from time import time

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
    def get(self):
        req = {'env:Envelope': self._get_soap_header(
                    resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
                    action='http://schemas.xmlsoap.org/ws/2004/09/transfer/Get')}
        req['env:Envelope']['env:Header'].pop('a:ReplyTo')
        req['env:Envelope'].setdefault('env:Body', {})
        print(xmltodict.unparse(req))
        res=self.send_message(xmltodict.unparse(req))
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

class CheckWinRMExceptionWARN(Exception):
    pass

class CheckWinRMExceptionCRIT(Exception):
    pass

class CheckWinRMExceptionUNKNOWN(Exception):
    pass


class WinRMScript:
    def __init__(self, hostaddress, auth, cleanup=True):
        if auth is None:
            raise CheckWinRMExceptionUNKNOWN("Authentication data missing")
        if 'domain' not in auth or auth['domain'] is None:
            raise CheckWinRMExceptionUNKNOWN("The user domain name is a mandatory argument")
        if 'username' not in auth or auth['username'] is None:
            raise CheckWinRMExceptionUNKNOWN("The username is a mandatory argument")
        if 'password' not in auth or auth['password'] is None:
            raise CheckWinRMExceptionUNKNOWN("The password is a mandatory argument")

        self.cleanup = cleanup
        self.data = {}
        self.hostaddress = hostaddress
        if 'upn' in auth:
            self.username = auth['username']
        else:
            self.username = auth['domain'] + '\\' + auth['username']
        self.password = auth['password']

    def open(self):
        self.p = WRProtocol(
            endpoint='http://%s:5985/wsman' % self.hostaddress,
            transport='ntlm',
            username=self.username,
            password=self.password)
        self.shell_id = self.p.open_shell()

    def close(self):
        self.p.cleanup_command(self.shell_id, self.command_id)
        self.p.close_shell(self.shell_id)

    def get_class(self, class_name):
        pass

    def send(self, command, expect_receive=True):
        res = self.p.send(self.shell_id, self.command_id, command + "\r\n")
        if expect_receive:
            res = self.p.receive(self.shell_id, self.command_id)
        else:
            res = ()
        return res

    def wmic(self):
        error = 0
        std_out = ''
        std_err = ''
        self.command_id = self.p.run_command(self.shell_id, 'wmic', [])
        return self.p.receive(self.shell_id, self.command_id)

    def posh(self, scriptline=None, scriptfile=None):
        script = None
        if scriptfile is not None:
            with open(scriptfile, "r") as f:
                script = f.read()
        elif scriptline is not None:
            script = scriptline
        if script is not None:
            encoded_ps = b64encode((variables + script).encode('utf_16_le')).decode('ascii')
            params = [ '-encodedcommand', encoded_ps ]
        else:
            params = []

        error = 0
        std_out = ''
        std_err = ''
        command_id = self.p.run_command(self.shell_id, 'powershell', params)
        self.check_error(std_err)

        if status_code != 0:
            raise CheckWinRMExceptionUNKNOWN(std_err)
        return "%s\n%s" % (std_out, "")

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
        for tag in root.findall('./ps:S', ns):
            t = tag.get('S')
            if t == 'Error':
                error = True
            msg += "%s : %s\n" % (t, tag.text.replace("_x000D__x000A_", ""))
        if error:
            raise CheckWinRMExceptionUNKNOWN(msg)
