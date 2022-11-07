import time

class SAMMCheck:
    def __init__(self, argv=None):
        self.outmsg = "UNKNOWN - Plugin has not been initialized"
        self.outval = 3
        self.ready = False
        self.done = False
        self.running = False
        self.start = 0
        self.stop = 0
        if argv is not None:
            self.process_args(argv)

    @property
    def runtime(self):
        return self.stop - self.start

    def process_args(self, argv):
        pass

    def run(self):
        pass

    def ok(self, msg, perf_data="", addl=""):
        self.outmsg = "OK - %s%s\n%s" % (msg, perf_data, addl)
        self.outval = 0
        self.done = True
        self.running = False
        self.stop = time.time()        


    def warning(self, msg, perf_data="", addl=""):
        self.outmsg = "WARNING - %s%s\n%s" % (msg, perf_data, addl)
        self.outval = 1
        self.done = True
        self.running = False
        self.stop = time.time()        

    def critical(self, msg, perf_data="", addl=""):
        self.outmsg = "CRITICAL - %s%s\n%s" % (msg, perf_data, addl)
        self.outval = 2
        self.done = True
        self.running = False
        self.stop = time.time()        

    def unknown(self, msg=None):
        if msg is not None:
            self.outmsg = "UNKNOWN - %s" % msg
        self.outval = 3
        self.done = True
        self.running = False
        self.stop = time.time()

    def __str__(self):
        return self.outmsg
