#!/usr/bin/python

import json

def application(environ, start_fn):
    indata=environ['PATH_INFO'].split('/')
    if len(indata) > 1:
        username=indata[1]
    else:
        username=''
    if username == '':
        start_fn('200 OK', [('Content-Type', 'text/html')])
        return [query_page()]
    else:
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps({'username': username})]
    return ["Hello World!\n<br>%s" % username]

def query_page():
    return '''
<HTML>
<HEAD><TITLE>Pre-Onboarding Console</TITLE>
<BODY>
    <H1><CENTER>Pre-Onboarding Console</CENTER></H1>
</BODY>
</HTML>
'''