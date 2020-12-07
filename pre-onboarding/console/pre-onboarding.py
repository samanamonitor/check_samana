#!/usr/bin/python

def app(environ, start_fn):
    start_fn('200 OK', [('Content-Type', 'text/plain')])
    return ["Hello World!\n"]