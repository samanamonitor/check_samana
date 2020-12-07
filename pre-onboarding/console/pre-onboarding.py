#!/usr/bin/python

def application(environ, start_fn):
    indata=environ['PATH_INFO'].split('/')
    start_fn('200 OK', [('Content-Type', 'text/plain')])
    return ["Hello World!\n<br>%s" % indata]