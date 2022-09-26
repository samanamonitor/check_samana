from winrm.protocol import Protocol
from base64 import b64encode
import xml.etree.ElementTree as ET

import xmltodict
import base64
import uuid


class WRProtocol(Protocol):
    def send(self, shell_id, command_id, stdin_input):
        req = {'env:Envelope': self._get_soap_header(
                    resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
                    action='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Send',  # NOQA
                    shell_id=shell_id)}
        stdin_envelope = req['env:Envelope'].setdefault('env:Body', {}).setdefault(
                    'rsp:Send', {}).setdefault('rsp:Stream', {})
        stdin_envelope['@CommandId'] = command_id
        stdin_envelope['@Name'] = 'stdin'
        stdin_envelope['@End'] = "false"
        stdin_envelope['@xmlns:rsp'] = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell'
        stdin_envelope['#text'] = base64.b64encode(stdin_input)
        return self.send_message(xmltodict.unparse(req))
    def receive(self, shell_id, command_id):
        req = {'env:Envelope': self._get_soap_header(
                    resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
                    action='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive',  # NOQA
                    shell_id=shell_id)}
        stream = req['env:Envelope'].setdefault('env:Body', {}).setdefault(
            'rsp:Receive', {}).setdefault('rsp:DesiredStream', {})
        stream['@CommandId'] = command_id
        stream['#text'] = 'stdout stderr'
        res = p.send_message(xmltodict.unparse(req))
        root = ET.fromstring(res)
        stream_nodes = [
            node for node in root.findall('.//*')
            if node.tag.endswith('Stream')]
        stdout = stderr = b''
        return_code = -1
        for stream_node in stream_nodes:
            if not stream_node.text:
                continue
            if stream_node.attrib['Name'] == 'stdout':
                stdout += base64.b64decode(stream_node.text.encode('ascii'))
            elif stream_node.attrib['Name'] == 'stderr':
                stderr += base64.b64decode(stream_node.text.encode('ascii'))
        command_done = len([
            node for node in root.findall('.//*')
            if node.get('State', '').endswith('CommandState/Done')]) == 1
        if command_done:
            return_code = int(
                next(node for node in root.findall('.//*')
                     if node.tag.endswith('ExitCode')).text)
        return stdout, stderr, return_code, command_done

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

    def open():
        self.p = Protocol(
            endpoint='http://%s:5985/wsman' % self.hostaddress,
            transport='ntlm',
            username=self.username,
            password=self.password)
        self.shell_id = self.p.open_shell()

    def close():
        p.cleanup_command(shell_id, command_id)
        p.close_shell(shell_id)

    def wmic(self):
        shell_id = None
        command_id = None
        p = None
        error = 0
        std_out = ''
        std_err = ''
        command_id = p.run_command(shell_id, 'wmic', [])
        std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
        self.check_error(std_err)

        if status_code != 0:
            raise CheckWinRMExceptionUNKNOWN(std_err)
        return "%s\n%s" % (std_out, "")

    def run(self, scriptline=''):
        if scriptfile is not None:
            with open(scriptfile, "r") as f:
                script = f.read()
        elif scriptline is not None:
            script = scriptline
        else:
            raise CheckWinRMExceptionUNKNOWN("Invalid script")

        shell_id = None
        command_id = None
        p = None
        error = 0
        std_out = ''
        std_err = ''
        encoded_ps = b64encode((variables + script).encode('utf_16_le')).decode('ascii')
        command_id = p.run_command(shell_id, 'powershell', ['-encodedcommand {0}'.format(encoded_ps), ])
        std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
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
