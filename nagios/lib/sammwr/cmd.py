from .winrmcommand import WinRMCommand

class CMDCommand(WinRMCommand):
    def __init__(self, *args, shell=None, cmd=None, params=[], **kwargs):
        WinRMCommand.__init__(self, *args, shell=shell, **kwargs)
        self.interactive = cmd is not None
        self.cmd=cmd
        self.params=params

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

