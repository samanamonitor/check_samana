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
            realm = None, scope = None, maxprotocol = None, user = None, no_pass = False, 
            password = None, authentication_file = None, signing = "off", machine_pass = False, 
            simple_bind_dn = None, kerberos = None, use_security_mechanisms = None, 
            namespace = None, timeout_sec = None):
        if wmi_class is None and query is None:
            raise WMIC_InvalidQuery
        if wmi_class is not None and query is not None:
            raise WMIC_InvalidQuery
        if host is None:
            raise WMIC_InvalidHost
        if timeout_sec is None:
            self._timeout_sec = 20
        else:
            self._timeout_sec = timeout_sec

        wmic_exec = '/usr/local/bin/wmic'
        self._command = [wmic_exec]
        if configfile is not None:
            self._command.append('--configfile')
            self._command.append(configfile)

        if len(option) > 0:
            for o in options:
                self._command.append('-option=%s' % o)

        if log_basename is not None:
            self._command.append('--log-basename')
            self._command.append(log_basename)

        if leak_report is not None and leak_report is True:
            self._command.append('--leak-report')

        if leak_report_full is not None and leak_report_full is True:
            self._command.append('--leak-report-full')

        if name_resolve is not None:
            self._command.append('--name-resolve')
            self._command.append(name_resolve)

        if socket_options is not None:
            self._command.append('--socket-options')
            self._command.append(socket_options)

        if netbiosname is not None:
            self._command.append('--netbiosname')
            self._command.append(netbiosname)

        if workgroup is not None:
            self._command.append('--workgroup')
            self._command.append(workgroup)

        if realm is not None:
            self._command.append('--realm=%s' % realm)

        if scope is not None:
            self._command.append('--scope')
            self._command.append(scope)
        if maxprotocol is not None:
            self._command.append('--maxprotocol')
            self._command.append(maxprotocol)

        if user is not None: # [DOMAIN\]USERNAME[%PASSWORD]]
            self._command.append('--user')
            self._command.append(user)

        if no_pass is True:
            self._command.append('--no-pass')

        if password is not None:
            self._command.append('--password=%s' % password)

        if authentication_file is not None:
            self._command.append('--authentication-file')
            self._command.append(authentication_file)

        if signing == "on" or signing == "required":
            self._command.append('--signing')
            self._command.append(signing)
        elif signing == "off":
            pass
        else:
            raise WMIC_InvalidSigning

        if machine_pass is not None and machine_pass is True:
            self._command.append('--machine-pass')

        if simple_bind_dn is not None:
            self._command.append('--simple-bind-dn=%s' % simple_bind_dn)

        if kerberos is not None:
            self._command.append('--kerberos')
            self._command.append(kerberos)

        if use_security_mechanisms is not None:
            self._command.append('--use-security-mechanisms=%s' % use_security_mechanisms)

        if namespace is not None:
            self._command.append('--namespace=%s' % namespace)

        self._command.append(host)

        if wmi_class is not None:
            query = "select * from %s" % wmi_class

        self._command.append(query)

    def get():
        p = subprocess.Popen(self._command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        with timeout(self.timeout_sec):
            output, err = p.communicate()
        print output

