#!/usr/bin/python

def application(environ, start_fn):
    indata=environ['PATH_INFO'].split('/')
    if len(indata > 1):
        username=indata[2]
    else:
        username=None
    start_fn('200 OK', [('Content-Type', 'text/plain')])
    return ["Hello World!\n<br>%s" % username]