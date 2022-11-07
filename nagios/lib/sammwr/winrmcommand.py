from .shell import WinRMShell

class WinRMCommand:
    def __init__(self, *args, shell=None, **kwargs):
        if shell is None:
            self.shell = WinRMShell(*args, **kwargs)
        else:
            if not isinstance(shell, WinRMShell):
                raise TypeError("Can only accept WinRMShell.")
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
            raise Exception("This is not an interactive session. Cannot exit")
        self.send_data = self.shell.send(self.command_id, 'exit\r\n', end=True)
    def __str__(self):
        return self.command_id

