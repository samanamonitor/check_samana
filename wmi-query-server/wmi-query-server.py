#!/usr/bin/python3

from cgi import parse_qs, escape
import json

def process_data(data):
    return data

def application (environ, start_response):
    data = {
        'hostaddress': None,
        'u_domain': None,
        'username': None,
        'password': None,
        'authfile': None,
        'nagiosaddress': None,
        'script': None,
        'warning': None,
        'critical': None,
        'url': None,
        'scriptarguments': None,
        'cleanup': True
    }

    d = parse_qs(environ['QUERY_STRING'])
    for k in data.keys():
        data[k] = d.get(k, [ None ])[0]
    response_body = json.dumps(process_data(d))

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

