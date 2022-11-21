#!/usr/bin/python3

import sys, getopt, os
sys.path.append('/usr/local/nagios/libexec/lib/python3/dist-packages')
from sammcheck import SAMMWorker
import time
import logging
import signal
from threading import Timer

w = None
keep_running = True

def log_stats():
    if not isinstance(w, SAMMWorker):
        logging.info("Object not defined yet. type=%s" % str(type(w)))
    else:
        logging.info(str(w.stats()))
    t=Timer(30.0, log_stats)


            "last_recv_job_id": self.last_recv_job_id,
            "last_run_job_id": self.last_run_job_id,
            "last_done_jobe_id": self.last_done_jobe_id,
            "received_jobs": self.received_jobs,
            "processed_jobs": self.processed_jobs,
            "run_jobs": self.run_jobs,
            "done_jobs": self.done_jobs
            "received_bytes": self.received_bytes,
            "running_jobs": len(self.running_jobs),
            "connected": self.connected,
            "registered": self.registered


def sig(signum, frame):
    global w
    global keep_running
    if signum == signal.SIGINT:
        logging.warning('Interrupt received. Closing connections')
        keep_running = False
        logging.shutdown()
    elif signum == signal.SIGHUP:
        w.registered = False
        logging.warning('Restarting the conneciton')
    else:
        logging.warning('Signal handler called with signal %s' % str(signum))

def help(msg=""):
    print("%s\n" \
        "USAGE: %s [ options ]\n" \
        "-F Run in the foreground\n" \
        "-r <seconds>  Delay between attempts of connection to worker pipe in seconds (def: 5 seconds)\n" \
        "-j <seconds>  Time to wait for jobs in seconds (def: 5 seconds)\n" \
        "-p <pid file> Path to the PID file (def: /run/sammworker_process.pid)\n" \
        "-u <username> Username to run this process (def: nagios)\n" \
        "-d <level>    Debug level\n" \
        "-h            Print this screen" % \
        (msg, sys.argv[0]))
    return -1

def main(argv):
    job_wait=5
    retry_delay=5
    pid_file='/run/sammworker_process.pid'
    runas='nagios'
    log_file="/usr/local/nagios/var/sammworker.log"
    qh_file='/usr/local/nagios/var/rw/nagios.qh'
    global keep_running

    try:
        opts, args = getopt.getopt(argv, "Fr:j:p:u:d:")
    except getopt.GetoptError:
        return help()

    foreground=False
    for opt, arg in opts:
        if opt == '-h':
            return help()
        elif opt == '-F':
            foreground = True
        elif opt == '-r':
            retry_delay = int(arg)
        elif opt == '-j':
            wait = int(arg)
        elif opt == '-p':
            pid_file = arg
        elif opt == '-u':
            runas = arg
        elif opt == '-d':
            logging.basicConfig(level=int(arg))
        else:
            return help("Invalid parameter %s" % arg)

    logging.basicConfig(level=logging.INFO, filename=log_file)
    if foreground == False:
        n = os.fork()
        if n > 0:
            return 0

    with open(pid_file, "w") as f:
        pid = os.getpid()
        f.write(str(pid))

    signal.signal(signal.SIGHUP, sig)
    signal.signal(signal.SIGINT, sig)

    log_stats()
    while keep_running:
        w = SAMMWorker(wait=job_wait)
        while w.connected == False:
            try:
                w.connect(qh_file)
                logging.info("Connected to Nagios. Starting to process requests")
            except:
                logging.warning("Nagios not running. Retrying in 5 seconds")
                time.sleep(retry_delay)
        w.register()
        if w.registered:
            logging.info("Registered")
        else:
            logging.critical("Unable to register. Aborting")
            w.close()
        while keep_running and w.registered and w.connected:
            try:
                if w.recv():
                    logging.debug("Received data.")
                else:
                    logging.debug("No data received. Check jobs.")
            except Exception as e:
                logging.warning("Unable to receive data. Exiting loop. %s" % str(e))
                continue
            for j in w.jobs:
                if w.run(j):
                    logging.debug("Ran job %s" % j)
            for j in w.jobs:
                if w.done(j):
                    logging.debug("Finished job %s" % j)
        logging.warning("Disconnected from Nagios.")
        w.close()
    os.remove(pid_file)
    return 0

if __name__ == "__main__":
    exit(main(sys.argv[1:]))
