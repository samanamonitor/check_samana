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
    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError):
        request_body_size = 0

    request_body = json.load(environ['wsgi.input'])


#    d = parse_qs(environ['QUERY_STRING'])
#    for k in data.keys():
#        data[k] = d.get(k, [ None ])[0]
    response_body = json.dumps(request_body)

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(response_body)))
    ]
    start_response(status, response_headers)

    return [response_body]

