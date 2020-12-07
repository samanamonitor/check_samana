#!/usr/bin/python

def application(environ, start_fn):
    start_fn('200 OK', [('Content-Type', 'text/plain')])
    return ["Hello World!\n<br>%s" % environ]