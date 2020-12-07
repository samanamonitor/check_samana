#!/usr/bin/python

def application(environ, start_fn):
    start_fn('200 OK %s' % environ, [('Content-Type', 'text/plain')])
    return ["Hello World!\n"]