from contextlib import contextmanager

class TimeoutError(Exception):
    pass

@contextmanager
def timeout(time):
`    signal.signal(signal.SIGALRM, raise_timeout)
    signal.alarm(time)

    try:
        yield
    except TimeoutError:
        raise
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)

def raise_timeout(signum, frame):
    raise TimeoutError

class WMIC_InvalidQuery(Exception):
    class

class WMIC:
    self._configfile = None
    self._option = {}
    self._log_basename = None
    self._leak_report = None
    self._leak_report_full = None
    self._name_resolve = None
    self._socket_options = None
    self._netbiosname = None
    self._workgroup = None
    self._realm = None
    self._scope = None
    self._maxprotocol = None
    self._user = None # [DOMAIN\]USERNAME[%PASSWORD]]
    self._no_pass = False
    self._password = None
    self._authentication_file = None
    self._signing = "off"
    self._machine_pass = None
    self._simple_bind_dn = None
    self._kerberos = None
    self._use_security_mechanisms = None
    self._namespace = None
    self._host = host
    self._query = None
    self._class = None
    self._parameters = None
    def __init__(self, host, wmi_class=None, query=None):
        if wmi_class is None and query is None:
            raise WMIC_InvalidQuery