#!/usr/bin/python3

from cgi import parse_qs, escape
import json

def process_data(data):
    return data

def application (environ, start_response):
    data = {
        "auth": {
            "username": "",
            "password": "",
            "domain": ""
        },
        "hostname": "",
        "etcdserver": "",
        "warning": -1,
        "critical": -1,
        "id-type": 0,
        "queries": []
    }

    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError):
        request_body_size = 0

    request_body = json.load(environ['wsgi.input'], size=request_body_size)

    res={"status": 0, "info1": "", "perf1": [], "info2": "", "perf2": []}
    response_body = json.dumps(res)

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

