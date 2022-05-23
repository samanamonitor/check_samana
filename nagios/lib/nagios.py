
class CheckException(Exception):
    def __init__(self, info=None, perf_data=None, addl=None, status=3, status_str="UNKNOWN"):
        self.result = CheckResult(info=info, perf_data=perf_data, addl=addl, status=status, status_str=status_str)

    def __str__(self):
        return str(self.result)

class CheckWarning(CheckException):
    def __init__(self, info=None, perf_data=None, addl=None):
        super().__init__(info, perf_data, addl, status=1, status_str='WARNING')

class CheckCritical(CheckException):
    def __init__(self, info=None, perf_data=None, addl=None):
        super().__init__(info, perf_data, addl, status=2, status_str='CRITICAL')

class CheckUnknown(CheckException):
    pass

class CheckResult():
    def __init__(self, info, perf_data=[], addl=None, status=0, status_str="OK"):
        self.info = info
        self.perf_data = perf_data
        self.addl = "\n%s" % addl if addl is not None else ""
        self.status = status
        self.status_str = status_str

    def __str__(self):
        perf = ""
        if isinstance(self.perf_data, list) and len(self.perf_data) > 0:
            perf = " | "
            perf += " ".join(self.perf_data)
        elif isinstance(self.perf_data, str):
            perf = " | %s" % self.perf_data

        addl = ""
        if self.addl is not None:
            addl = "\n%s" % self.addl
        return "%s - %s%s%s" % (self.status_str, self.info, perf, addl)
