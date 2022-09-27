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

class CheckWinRMExceptionWARN(Exception):
    pass

class CheckWinRMExceptionCRIT(Exception):
    pass

class CheckWinRMExceptionUNKNOWN(Exception):
    pass


class WinRMScript:
    def __init__(self, cleanup=True):
        self.cleanup = cleanup
        self.data = {}
        self.shell_id = None
        self.command_id = None

    def open(self, hostaddress, auth):
        if auth is None:
            raise CheckWinRMExceptionUNKNOWN("Authentication data missing")
        if 'domain' not in auth or auth['domain'] is None:
            raise CheckWinRMExceptionUNKNOWN("The user domain name is a mandatory argument")
        if 'username' not in auth or auth['username'] is None:
            raise CheckWinRMExceptionUNKNOWN("The username is a mandatory argument")
        if 'password' not in auth or auth['password'] is None:
            raise CheckWinRMExceptionUNKNOWN("The password is a mandatory argument")

        self.hostaddress = hostaddress
        if 'upn' in auth:
            self.username = auth['username']
        else:
            self.username = auth['domain'] + '\\' + auth['username']
        self.password = auth['password']
        self.p = WRProtocol(
            endpoint='http://%s:5985/wsman' % self.hostaddress,
            transport='ntlm',
            username=self.username,
            password=self.password)
        self.shell_id = self.p.open_shell()

    def close(self):
        if self.command_id is not None:
            command_id=self.command_id
            self.command_id = None
            self.p.cleanup_command(self.shell_id, command_id)
        self.p.close_shell(self.shell_id)
        self.shell_id = None

    def get_class(self, class_name, class_filter=None):
        cmd="PATH %s" % class_name
        if class_filter is not None:
            cmd += " WHERE " + class_filter
        res=self.send(cmd + " GET /format:rawxml")
        return res
        
    def exit(self):
        return self.p.send(self.shell_id, self.command_id, 'exit\r\n', end=True)

    def send(self, command, expect_receive=True, end=False):
        res = self.p.send(self.shell_id, self.command_id, command + "\r\n", end)
        if expect_receive:
            res = self.p.receive(self.shell_id, self.command_id)
        else:
            res = ()
        return res

    def receive(self, interactive=False):
        stdin_data = ''
        stderr_data = ''
        total_time = 0
        while True:
            res=self.p.receive(self.shell_id, self.command_id)
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

    def wmic(self, class_name=None, class_filter=None):
        params=[]
        interactive=True
        if class_name is not None:
            interactive = False
            params += [ 'PATH', class_name ]
            if class_filter is not None:
                params += [ 'WHERE', class_filter ]
            params += [ 'GET', '/FORMAT:RAWXML' ]
        self.command_id = self.p.run_command(self.shell_id, 'wmic', params)
        res = self.receive(interactive)
        print(res)
        if class_name is not None:
            root = ET.fromstringlist(res[0].replace('\r','').split('\n')[:-1])
            data={}
            for property in root.findall(".//PROPERTY"):
              n=property.attrib['NAME']
              v=property.find("./VALUE")
              data[n]=v.text if v is not None else None
              res += (data,)

        return res

    def cmd(self, params=[], interactive=False):
        if len(params) == 0:
            interactive = True
        self.command_id = self.p.run_command(self.shell_id, 'cmd', params)
        res=self.receive(interactive)
        return res

    def posh(self, scriptline=None, scriptfile=None):
        script = None
        if scriptfile is not None:
            with open(scriptfile, "r") as f:
                script = f.read()
        elif scriptline is not None:
            script = scriptline
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
        return (res[0], err, res[2], res[3], res[4])

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
        msg = "Error executing Powershell Command.\n"
        error = False
        for tag in root.findall('./ps:S', ns):
            t = tag.get('S')
            if t == 'Error':
                error = True
            msg += "%s : %s\n" % (t, tag.text)
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
        for tag in root.findall('./ps:S', ns):
            t = tag.get('S')
            if t == 'Error':
                error = True
            msg += "%s : %s\n" % (t, tag.text.replace("_x000D__x000A_", ""))
        if error:
            raise CheckWinRMExceptionUNKNOWN(msg)
