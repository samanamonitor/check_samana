from winrm.protocol import Protocol
from winrm.exceptions import WinRMTransportError
from base64 import b64encode
import xml.etree.ElementTree as ET
from time import time
import os

import xmltodict
import base64
import uuid

class WRError(Exception):
    code = 500
    @property
    def response_text(self):
        return self.args[1]

    @property
    def fault_data(self):
        return self.args[2]
    
    @property
    def fault_detail(self):
        return self.args[3]
    

class WRProtocol(Protocol):
    xmlns = {
        'a': "http://schemas.xmlsoap.org/ws/2004/08/addressing",
        's': "http://www.w3.org/2003/05/soap-envelope",
        'w': "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd",
        'rsp': "http://schemas.microsoft.com/wbem/wsman/1/windows/shell",
        'p': "http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd",
        'wsen': "http://schemas.xmlsoap.org/ws/2004/09/enumeration",
        'wsmanfault': "http://schemas.microsoft.com/wbem/wsman/1/wsmanfault",
        'wsmv': 'http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd'
    }

    def send_message(self, message):
        # TODO add message_id vs relates_to checking
        # TODO port error handling code
        try:
            resp = self.transport.send_message(message)
            return resp
        except WinRMTransportError as ex:
            try:
                # if response is XML-parseable, it's probably a SOAP fault; extract the details
                root = ET.fromstring(ex.response_text)
            except Exception:
                # assume some other transport error; raise the original exception
                raise ex

            fault = root.find('s:Body/s:Fault', self.xmlns)
            if fault is not None:
                fault_data = dict(
                    transport_message=ex.message,
                    http_status_code=ex.code
                )
                wsmanfault_code = fault.find('s:Detail/wsmanfault:WSManFault[@Code]', self.xmlns)
                if wsmanfault_code is not None:
                    fault_data['wsmanfault_code'] = wsmanfault_code.get('Code')
                    # convert receive timeout code to WinRMOperationTimeoutError
                    if fault_data['wsmanfault_code'] == '2150858793':
                        # TODO: this fault code is specific to the Receive operation; convert all op timeouts?
                        raise WinRMOperationTimeoutError()

                fault_code = fault.find('s:Code/s:Value', self.xmlns)
                if fault_code is not None:
                    fault_data['fault_code'] = fault_code.text

                fault_subcode = fault.find('s:Code/s:Subcode/s:Value', self.xmlns)
                if fault_subcode is not None:
                    fault_data['fault_subcode'] = fault_subcode.text

                error_message = fault.find('s:Reason/s:Text', self.xmlns)
                if error_message is not None:
                    error_message = error_message.text
                else:
                    error_message = "(no error message in fault)"

                fault_detail = fault.find('s:Detail', self.xmlns)

                raise WRError('{0} (extended fault data: {1})'.format(error_message, fault_data), \
                    ex.response_text,
                    fault_data, fault_detail)

    def pull(self, shell_id, resource_uri, enumeration_ctx, max_elements=10):
        message_id = uuid.uuid4()
        req = {
            'env:Envelope': self._get_soap_header(
            resource_uri=resource_uri,  # NOQA
            action='http://schemas.xmlsoap.org/ws/2004/09/enumeration/Pull')}
        req['env:Envelope'].setdefault('env:Body', {}).setdefault(
            'n:Pull', {
                'n:EnumerationContext': enumeration_ctx,
                'n:MaxElements': max_elements
            })
        #print(xmltodict.unparse(req))
        try:
            res=self.send_message(xmltodict.unparse(req))
        except Exception as e:
            return e
        return res

    def enumerate(self, shell_id, resource_uri, en_filter=None, wql=None):
        message_id = uuid.uuid4()
        req = {
            'env:Envelope': self._get_soap_header(
            resource_uri=resource_uri,  # NOQA
            action='http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate')}
        req['env:Envelope'].setdefault('env:Body', {}).setdefault('n:Enumerate', {})
        if wql is not None:
            req['env:Envelope']['env:Body']['n:Enumerate']['w:Filter'] = {
                '@Dialect': 'http://schemas.microsoft.com/wbem/wsman/1/WQL',
                '#text': wql
            }

        elif en_filter is not None:
            req['env:Envelope']['env:Body']['n:Enumerate']['w:Filter'] = {
                '@Dialect': 'http://schemas.dmtf.org/wbem/wsman/1/wsman/SelectorFilter',
                'w:SelectorSet': { 
                    'w:Selector': [ { '@Name': k, '#text': en_filter[k]} for k in en_filter ] }
                }
        #print(xmltodict.unparse(req))
        try:
            res=self.send_message(xmltodict.unparse(req))
        except Exception as e:
            return e
        return res

    def get(self, shell_id, resource_uri):
        message_id = uuid.uuid4()
        req = {
            'env:Envelope': self._get_soap_header(
            resource_uri=resource_uri,  # NOQA
            action='http://schemas.xmlsoap.org/ws/2004/09/transfer/Get')}
        #req['env:Envelope']['env:Header']['w:SelectorSet'] = {
        #    'w:Selector': { '@Name': 'id', '#text': '1'}
        #    }
        req['env:Envelope'].setdefault('env:Body', {})
        try:
            res=self.send_message(xmltodict.unparse(req))
        except Exception as e:
            return e
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
        stream_stdout = root.findall('.//rsp:Stream[@Name=\'stdout\']', self.xmlns)
        for stream_node in stream_stdout:
            if stream_node.text is not None:
                stdout += base64.b64decode(stream_node.text.encode('ascii'))
        stream_stderr = root.findall('.//rsp:Stream[@Name=\'stderr\']', self.xmlns)
        for stream_node in stream_stderr:
            if stream_node.text is not None:
                stderr += base64.b64decode(stream_node.text.encode('ascii'))

        cs=root.find('.//rsp:CommandState[@State=\'%(rsp)s/CommandState/Done\']' % self.xmlns, self.xmlns)
        command_done = cs is not None
        ec=root.find('.//rsp:ExitCode', self.xmlns)
        if ec is not None:
            return_code = int(ec.text)
        else:
            return_code = -1
        return stdout, stderr, return_code, command_done, total_time

class ExceptionWinRMCommandNonInteractive(Exception):
    pass

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
        if self.code != 0:
            self.error=True

    def exit(self):
        if not self.interactive:
            raise ExceptionWinRMCommandNonInteractive()
        self.send_data = self.shell.send(self.command_id, 'exit\r\n', end=True)
    def __str__(self):
        return self.command_id

class WMIQuery(WinRMCommand):
    xmlns = {
        'xsi': "http://www.w3.org/2001/XMLSchema-instance",
        'b': "http://schemas.dmtf.org/wbem/wsman/1/cimbinding.xsd",
        'p': "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/MSFT_WmiError",
        'cim': "http://schemas.dmtf.org/wbem/wscim/1/common"
    }
    base_uri='http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/'
    def get_class(self, class_name):
        try:
            self._class_data = self.shell.get(self.base_uri + class_name)
        except WRError as e:
            print("FB:"+e.fault_detail)
            error_code = e.fault_detail.find('p:MSFT_WmiError/p:error_Code')
            if error_code is not None and error_code.text == '2150859002':
                return self.enumerate_class(class_name)
            return e
        except Exception as e:
            return e

        try:
            self._root = ET.fromstring(self._class_data)
            xmlns = {
                's': self.shell.p.xmlns['s'],
                'p': self.base_uri + class_name,
                'cim': "http://schemas.dmtf.org/wbem/wscim/1/common"
            }
            nil = '{http://www.w3.org/2001/XMLSchema-instance}nil'
            xmldata=self._root.find('s:Body/p:%s', xmlns)
            data = self.xmltodict(xmldata)
            return data
        except Exception as e:
            return e

    def wql(self, wql):
        return self.enumerate_class('*', wql=wql)

    def enumerate_class(self, class_name, en_filter=None, wql=None):
        self.resource_uri = self.base_uri + class_name
        try:
            self._class_data = self.shell.enumerate(self.resource_uri, en_filter=en_filter, wql=wql)
        except WRError as e:
            return e

        xmlns = {
            's': "http://www.w3.org/2003/05/soap-envelope",
            'p': self.resource_uri,
            'n': "http://schemas.xmlsoap.org/ws/2004/09/enumeration",
            'xsi': "http://www.w3.org/2001/XMLSchema-instance"
        }
        try:
            self._root = ET.fromstring(self._class_data)
            self._ec = self._root.find('s:Body/n:EnumerateResponse/n:EnumerationContext', xmlns).text
        except Exception as e:
            return e

        data = []
        while True:
            try:
                self.ec_data = self.shell.pull(self.resource_uri, self._ec)
            except WRError as e:
                return e

            try:
                self._pullresponse = ET.fromstring(self.ec_data)
            except Exception as e:
                return e

            items = self._pullresponse.findall('s:Body/n:PullResponse/n:Items/', xmlns)
            for item in items:
                data += [self.xmltodict(item, class_name, xmlns)]

            if self._pullresponse.find('s:Body/n:PullResponse/n:EndOfSequence', xmlns) is not None:
                break
            _ec = self._pullresponse.find('s:Body/n:PullResponse/n:EnumerationContext', xmlns)
            if _ec is None:
                raise WRError("Invalid EnumerationContext.")
            self._ec = _ec.text
        return data


    def xmltodict(self, data_root, class_name, xmlns):
        data = {}
        for i in data_root.findall('./'):
            tagname = i.tag.split('}')[1]
            nil = "{%s}nil" % xmlns['xsi']
            if i.attrib.get(nil, 'false') == 'true':
                data[tagname] = None
            else:
                if i.text is not None:
                    data[tagname] = i.text
                else:
                    data[tagname]={}
                    for e in i.findall('./'):
                        # TODO: improve this to remove namespace
                        e_tagname=e.tag.split('}')
                        if len(e_tagname) > 1:
                            e_tagname = e_tagname[1]
                        else:
                            e_tagname = e_tagname[0]

                        data[tagname][e_tagname] = e.text
        return data

class CMDCommand(WinRMCommand):
    def __init__(self, shell, cmd=None, params=[]):
        WinRMCommand.__init__(self, shell)
        self.interactive = cmd is not None
        self.cmd=cmd
        self.params=params
        self.shell = shell

    def run(self):
        self.error = False
        if self.cmd is None:
            self.interactive = True
            self.command_id = self.shell.run_command("cmd", [])
        else:
            self.interactive = False
            self.command_id = self.shell.run_command(self.cmd, self.params)
        self.receive()

    def __repr__(self):
        return "<%s interactive=%s code=%d std_out_bytes=%d std_err_bytes=%d>" % \
            (self.__class__.__name__, self.interactive, self.code,
                len(self.std_out), len(self.std_err))

class WMICommand(WinRMCommand):
    def __init__(self, shell, class_name=None, class_filter=None):
        WinRMCommand.__init__(self, shell)
        self.class_name = class_name
        self.class_filter = class_filter
        self.interactive = self.class_name is not None

    def run(self):
        params = []
        self.error = False
        if self.class_name is not None:
            params += [ 'PATH', self.class_name ]
            if self.class_filter is not None:
                params += [ 'WHERE', self.class_filter ]
            params += [ 'GET', '/FORMAT:RAWXML' ]
        self.command_id = self.shell.run_command('wmic', params)
        self.receive()
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

    def __repr__(self):
        return "<%s interactive=%s code=%d%s%s error=%s std_out_bytes=%d std_err_bytes=%d>" % \
            (self.__class__.__name__, self.interactive, self.code,
                " class_name=%s" % self.class_name if self.class_name is not None else "",
                " class_filter=%s" % self.class_filter if self.class_filter is not None else "",
                self.error,
                len(self.std_out), len(self.std_err))

class POSHCommand(WinRMCommand):
    def __init__(self, shell, scriptline=None, scriptfile=None):
        WinRMCommand.__init__(self, shell)
        self.scriptfile=scriptfile
        self.scriptline=scriptline
        self.posh_error=''

    def run(self):
        script = None
        if self.scriptfile is not None:
            with open(self.scriptfile, "r") as f:
                script = "$ProgressPreference = \"SilentlyContinue\";" + f.read()
        elif self.scriptline is not None:
            script = "$ProgressPreference = \"SilentlyContinue\";" + self.scriptline
        if script is not None:
            self.interactive = False
            encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
            params = [ '-encodedcommand', encoded_ps ]
        else:
            self.interactive = True
            params = []

        self.command_id = self.shell.run_command('powershell', params)
        self.receive()
        self.decode_posh_error()

    def decode_posh_error(self):
        if len(self.std_err) == 0:
            return
        if self.std_err[0] == '#':
            temp = self.std_err.split('\n', 1)
            if len(temp) < 2:
                return
        try:
            root = ET.fromstring(temp[1])
        except ET.ParseError:
            return
        ns={ 'ps':root.tag.split('}')[0].split('{')[1] }
        self.posh_error = ""
        error = False
        for tag in root.findall('./ps:S', ns):
            t = tag.get('S')
            if t == 'Error':
                self.error = True
            self.posh_error += "%s : %s" % (t, tag.text.replace("_x000D__x000A_", "\n"))

    def __repr__(self):
        return "<%s interactive=%s code=%d error=%s std_out_bytes=%d std_err_bytes=%d>" % \
            (self.__class__.__name__, self.interactive,
                self.code, self.error,
                len(self.std_out), len(self.std_err))

class ExceptionWinRMShellNotConnected(Exception):
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
            raise ExceptionWinRMShellNotConnected()
        return self.p.run_command(self.shell_id, cmd, params)

    def __str__(self):
        return self.shell_id

    def __repr__(self):
        return "<%s connected=%s hostaddress=%s username=%s domain=%s shell_id=%s>" % \
            (self.__class__.__name__, self.connected, self.hostaddress, \
                self.username, self.domain, self.shell_id)

    def close(self):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
        self.p.close_shell(self.shell_id)
        self.shell_id = None
        self.connected = False

    def get(self, resource_uri):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
        return self.p.get(self.shell_id, resource_uri)        

    def enumerate(self, resource_uri, en_filter=None, wql=None):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
        return self.p.enumerate(self.shell_id, resource_uri, en_filter=en_filter, wql=wql)        

    def pull(self, resource_uri, enumeration_ctx):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
        return self.p.pull(self.shell_id, resource_uri, enumeration_ctx)        

    def signal(self, command_id, s):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
        return self.p.signal(self.shell_id, command_id, s)

    def send(self, command, expect_receive=True, end=False):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
        self.send_res = self.p.send(self.shell_id, self.command_id, command + "\r\n", end)
        if expect_receive:
            return self.p.receive(self.shell_id, self.command_id)
        else:
            return None

    def receive(self, command_id, interactive=False):
        if not self.connected:
            raise ExceptionWinRMShellNotConnected()
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


