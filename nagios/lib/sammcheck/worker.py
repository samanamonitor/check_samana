import socket, select
import os, signal, sys
import time
import logging
from .check import SAMMCheck
from .etcdcheck import SAMMEtcdCheck
from threading import Thread

def str2array(a):
    arr=[]
    s=''
    quote = False
    escape = False
    for i in a:
        if not escape:
            if i == ' ' and not quote:
                arr += [s]
                s = ''
                continue
            elif i == '\\':
                escape = True
                continue
            elif i == '\'' or i == '"':
                quote = not quote
                continue
        if escape:
            if i != ' ' and i != '\\' and i != '\'' and i != '"':
                s += "\\"
        s += i
    if s != '':
        arr += [s]
    return arr

class SAMMWorker:
    def __init__(self, sock=None, wait=5):
        if sock is None:
            self.sock = socket.socket(
                            socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.pid = os.getpid()
        self.registered = False
        self.connected = False
        self.max_jobs = 1
        self.running_jobs = {}
        self.raw_data = b""
        self.wait = wait
        self.last_recv_job_id=-1
        self.last_run_job_id=-1
        self.last_done_jobe_id=-1
        self.received_jobs=0
        self.processed_jobs=0
        self.received_bytes=0
        self.sent_bytes=0
        logging.debug("Instantiation of NagiosWorker with sock=%s and wait=%d", \
            self.sock, self.wait)

    def connect(self, address):
        self.sock.connect(address)
        logging.debug("Connected to address \"%s\"", address)
        self.connected = True

    def stats(self):
        return {
            "lastpid": self.lastpid
            "running_jobs": len(self.running_jobs)
            "connected": self.connected
            "registered": self.registered
        }

    def register(self):
        self.register_message=b'@wproc register name=test %(pid)d;pid=%(pid)d;' \
            b'max_jobs=%(max_jobs)d;plugin=check_samana4\0\1\0\0\0' \
            % {b'pid': self.pid, b'max_jobs': self.max_jobs}
        logging.debug("Sending registration message: \"%s\"", self.register_message.decode('ascii'))
        self.sock.send(self.register_message)
        rec = self.sock.recv(3)
        logging.debug("Received data: %s", rec.decode('ascii'))
        if b"OK\0" != rec:
            raise Exception("Error Connecting. " + rec.decode('ascii'))
        self.registered=True

    def detach(self):
        self.sock = self.sock.detach()
        logging.debug("Detached sock %s", str(self.sock))

    def close(self):
        self.connected = False
        self.registered = False
        self.sock.close()
        logging.debug("Closed sock %s", str(self.sock))

    def recv(self):
        if self.connected == False:
            raise Exception("Not connected")
        readsock, writesock, exsock = select.select([self.sock], [], [], self.wait)
        logging.debug("Select releasing: readsock=%s", str(readsock))
        if len(readsock) > 0:
            temp=readsock[0].recv(2048)
            self.received_bytes=len(temp)
            self.raw_data += temp
            if self.raw_data == b"":
                self.registered = False
                raise Exception("Got disconnected?")
            if not isinstance(self.raw_data, bytes):
                raise Exception("Invalid input from nagios")
            self.raw_data = self.process(self.raw_data.decode('ascii'))
            return True
        return False

    def process(self, s):
        reclist=s.split("\0\1\0\0\0")
        if s[-5:] != '\x00\x01\x00\x00\x00':
            remaining_data = reclist[-1]
            reclist = reclist[:-1]
        else:
            remaining_data = ""
        self.received_jobs+=len(reclist)
        for rec in reclist:
            if rec == '':
                continue
            self.processed_jobs+=1
            data={}
            param_list=rec.split('\0')
            for p in param_list:
                if '=' not in p:
                    continue
                (k,v) = p.split('=')
                data[k] = v
            if 'job_id' not in data:
                raise Exception("Invalid input." + rec)
            self.last_recv_job_id = data['job_id']
            self.running_jobs[data['job_id']] = data
            command = data['command']
            #logging.info(command)
            data['argv'] = str2array(command)
            plugin=data['argv'][0].split('/')[-1]
            if plugin == "check_samana4":
                data['check'] = SAMMEtcdCheck(data['argv'][1:])
            else:
                data['check'] = SAMMCheck(data['argv'][1:])
        return remaining_data.encode('ascii')

    def run(self, job_id):
        job = self.running_jobs[job_id]
        check = job['check']
        self.last_run_job_id=job_id
        if not check.running and not check.done:
            job['thread'] = Thread(target=check.run, args=())
            job['thread'].start()
            return True
            #logging.info(check)
        return False

    def done(self, job_id):
        if job_id not in self.running_jobs:
            raise Exception("Job %s not pending" % str(jdi))
        job = self.running_jobs[job_id]
        if job['thread'].is_alive():
            return False
        check = job['check']
        if not check.done:
            data = {
                b'job_id': job_id.encode('ascii'),
                b'type': job['type'].encode('ascii'),
                b'start': check.start,
                b'stop': check.stop,
                b'runtime': check.runtime,
                b'outstd': str(check).encode('ascii'),
                b'outerr': b'Some error happened',
                b'exited_ok': 0,
                b'wait_status': check.outval * 0x100
            }
        else:
            data = {
                b'job_id': job_id.encode('ascii'),
                b'type': job['type'].encode('ascii'),
                b'start': check.start,
                b'stop': check.stop,
                b'runtime': check.runtime,
                b'outstd': str(check).encode('ascii'),
                b'outerr': '',
                b'exited_ok': 1,
                b'wait_status': check.outval * 0x100
        }
        message=b'job_id=%(job_id)s\0type=%(type)s\0start=%(start)f\0' \
            b'stop=%(stop)f\0runtime=%(runtime)f\0outstd=%(outstd)s\0' \
            b'wait_status=%(wait_status)d\0exited_ok=%(exited_ok)d\0' \
            b'outerr=%(outerr)s\0\1\0\0\0' % data
        self.sock.send(message)
        #print(message.decode('ascii'))
        self.running_jobs.pop(job_id)
        self.last_done_jobe_id=job_id
        return True

    @property
    def jobs(self):
        return [k for k in self.running_jobs.keys()]

