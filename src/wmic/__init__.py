from contextlib import contextmanager
import subprocess
import signal

class TimeoutError(Exception):
    pass

@contextmanager
def timeout(time):
    signal.signal(signal.SIGALRM, raise_timeout)
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
    pass

class WMIC_InvalidHost(Exception):
    pass

class WMIC_InvalidSigning(Exception):
    pass

class Client:
    def __init__(self, host, wmi_class=None, query=None, timeout=60, configfile=None,
            option=[], log_basename=None, leak_report=None, leak_report_full=None, 
            name_resolve = None, socket_options = None, netbiosname = None, workgroup = None, 
            realm = None, scope = None, maxprotocol = None, user = None, no_pass = True, 
            password = None, authentication_file = None, signing = "off", machine_pass = False, 
            simple_bind_dn = None, kerberos = None, use_security_mechanisms = None, 
            namespace = None, timeout_sec = None):
        self.host = host
        self.wmi_class=wmi_class, 
        self.query=query
        self.timeout=timeout
        self.configfile=configfile
        self.option=option
        self.log_basename=log_basename
        self.leak_report=leak_report
        self.leak_report_full=leak_report_full
        self.name_resolve = name_resolve
        self.socket_options = socket_options
        self.netbiosname = netbiosname
        self.workgroup = workgroup
        self.realm = realm
        self.scope = scope
        self.maxprotocol = maxprotocol
        self.user = user
        self.no_pass = no_pass
        self.password = password
        self.authentication_file = authentication_file
        self.signing = signing
        self.machine_pass = machine_pass
        self.simple_bind_dn = simple_bind_dn
        self.kerberos = kerberos
        self.use_security_mechanisms = use_security_mechanisms
        self.namespace = namespace
        self.timeout_sec = timeout_sec



    def _prepare_command(self):
        if self.wmi_class is None and self.query is None:
            raise WMIC_InvalidQuery
        if self.wmi_class is not None and self.query is not None:
            raise WMIC_InvalidQuery
        if self.host is None:
            raise WMIC_InvalidHost
        if self.timeout_sec is None:
            self._timeout_sec = 20
        else:
            self._timeout_sec = timeout_sec

        wmic_exec = '/usr/local/bin/wmic'
        self._command = [wmic_exec]
        if self.configfile is not None:
            self._command.append('--configfile')
            self._command.append(configfile)

        if len(self.option) > 0:
            for o in self.options:
                self._command.append('-option=%s' % o)

        if self.log_basename is not None:
            self._command.append('--log-basename')
            self._command.append(self.log_basename)

        if self.leak_report is not None and self.leak_report is True:
            self._command.append('--leak-report')

        if self.leak_report_full is not None and self.leak_report_full is True:
            self._command.append('--leak-report-full')

        if self.name_resolve is not None:
            self._command.append('--name-resolve')
            self._command.append(self.name_resolve)

        if self.socket_options is not None:
            self._command.append('--socket-options')
            self._command.append(self.socket_options)

        if self.netbiosname is not None:
            self._command.append('--netbiosname')
            self._command.append(self.netbiosname)

        if self.workgroup is not None:
            self._command.append('--workgroup')
            self._command.append(self.workgroup)

        if self.realm is not None:
            self._command.append('--realm=%s' % self.realm)

        if self.scope is not None:
            self._command.append('--scope')
            self._command.append(self.scope)
        if self.maxprotocol is not None:
            self._command.append('--maxprotocol')
            self._command.append(self.maxprotocol)

        if self.user is not None: # [DOMAIN\]USERNAME[%PASSWORD]]
            self._command.append('--user')
            self._command.append(self.user)

        if self.password is not None:
            self.no_pass = False
            self._command.append('--password=%s' % self.password)

        if self.no_pass is True:
            self._command.append('--no-pass')

        if self.authentication_file is not None:
            self._command.append('--authentication-file')
            self._command.append(self.authentication_file)

        if self.signing == "on" or self.signing == "required":
            self._command.append('--signing')
            self._command.append(self.signing)
        elif self.signing == "off":
            pass
        else:
            raise WMIC_InvalidSigning

        if self.machine_pass is not None and self.machine_pass is True:
            self._command.append('--machine-pass')

        if self.simple_bind_dn is not None:
            self._command.append('--simple-bind-dn=%s' % self.simple_bind_dn)

        if self.kerberos is not None:
            self._command.append('--kerberos')
            self._command.append(self.kerberos)

        if self.use_security_mechanisms is not None:
            self._command.append('--use-security-mechanisms=%s' % self.use_security_mechanisms)

        if self.namespace is not None:
            self._command.append('--namespace=%s' % self.namespace)

        self._command.append("//%s" % host)

        if self.wmi_class is not None:
            self.query = "select * from %s" % self.wmi_class

        self._command.append(self.query)

    def get(self):
        self._prepare_command()
        p = subprocess.Popen(self._command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        with timeout(self._timeout_sec):
            output, err = p.communicate()
        print output

