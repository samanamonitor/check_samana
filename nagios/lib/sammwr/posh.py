from .winrmcommand import WinRMCommand
from base64 import b64encode

class POSHCommand(WinRMCommand):
    def __init__(self, *args, shell=None, scriptline=None, scriptfile=None, **kwargs):
        WinRMCommand.__init__(self, *args, shell=shell, **kwargs)
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

