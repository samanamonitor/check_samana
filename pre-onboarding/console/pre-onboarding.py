#!/usr/bin/python

import json

def application(environ, start_fn):
    indata=environ['PATH_INFO'].split('/')
    if len(indata) > 1:
        func=indata[1]
    else:
        func=''
    if len(indata) > 2:
        search_data=indata[2]
    else:
        search_data=None

    if func == '':
        start_fn('200 OK', [('Content-Type', 'text/html')])
        return [query_page()]
    elif func == 'userdata':
        user_sid = get_user_sid(search_data)
        if user_sid is None:
            start_fn('400 INVALID USER SID', [('Content-Type', 'text/plain')])
            return ["Invalid function %s\n" % func]
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps({'username': search_data, 'sid': user_sid})]
    elif func == "xml":
        xmldata = get_user_xmldata(search_data)
        if xmldata is None:
            start_fn('400 INVALID USER SID', [('Content-Type', 'text/plain')])
            return ["Invalid user SID %s\n" % search_data]
        start_fn('200 OK', [('Content-Type', 'application/xml')])
        return [ str(xmldata) ]
    elif func == "printers":
        xmldata = get_user_xmldata(search_data)
        if xmldata is None:
            start_fn('400 INVALID USER SID', [('Content-Type', 'text/plain')])
            return ["Invalid user SID %s\n" % search_data]
        printers = get_printers(xmldata)
        if printers is None:
            start_fn('400 INVALID USER SID', [('Content-Type', 'text/plain')])
            return ["Invalid user SID %s\n" % search_data]
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [ json.dumps(printers) ]
    else:
        start_fn('400 INVALID FUNC', [('Content-Type', 'text/plain')])
        return ["Invalid function %s\n" % func]

def query_page():
    return '''
<HTML>
<HEAD><TITLE>Pre-Onboarding Console</TITLE>
<BODY>
    <H1><CENTER>Pre-Onboarding Console</CENTER></H1>
</BODY>
</HTML>
'''

def pairwise(iterable):
    "s -> (s0, s1), (s2, s3), (s4, s5), ..."
    a = iter(iterable)
    return izip(a, a)

def xml_2_hash(property_list):
    out = {}
    for p in property_list:
        out[p.name] = p.text
    return out

def get_printers(xmltxt):
    from itertools import izip
    import xml.etree.ElementTree as et
    tree = et.fromstring(xmltxt)
    root = tree.getroot()
    if root[0].attrib['Type'] != "System.Collections.HashTable":
        print "Invalid XML"
        return None
    printers = []
    for k,v in pairwise(root[0]):
        if k.text == "printers" and v.attrib['Type'] == "System.Object[]":
            for p in v:
                printers += xml_2_hash(v)
            break
    return printers


def get_user_xmldata(objectSid):
    import etcd
    client = etcd.Client(port=2379)
    try:
        data_b64 = client.get('/pre-onboarding/%s' % objectSid).value
    except EtcdKeyNotFound:
        print "User not found"
        return None
    import base64
    data = base64.b64decode(data_b64)
    return data.decode("UTF-16")

def get_user_sid(samaccountname):
    import ldap
    l = ldap.initialize('ldap://snv.net')
    username = "xd931@snv.net"
    password = "C.aes3dsT6zZ"
    l.protocol_version = ldap.VERSION3
    l.simple_bind_s(username, password)
    basedn='dc=snv,dc=net'
    searchFilter="(samAccountName=%s)" % samaccountname
    searchAttribute=["objectSid"]
    searchScope=ldap.SCOPE_SUBTREE
    search_id = l.search(basedn, searchScope, searchFilter, searchAttribute)
    search_result = l.result(search_id, 0)
    try:
        objectSid = search_result[1][0][1]['objectSid'][0]
    except IndexError:
        print "Invalid ldap result"
        return None
    except TypeError:
        print "Invalid ldap result"
        return None
    return convert_sid_bin_txt(objectSid)


def convert_sid_bin_txt(binary):
    '''
    code taken from: https://stackoverflow.com/questions/33188413/python-code-to-convert-from-objectsid-to-sid-representation
    page references: http://blogs.msdn.com/b/oldnewthing/archive/2004/03/15/89753.aspx
    and: http://codeimpossible.com/2008/04/07/Converting-a-Security-Identifier-from-binary-to-string/
'''
    import struct
    version = struct.unpack('B', binary[0])[0]
    # I do not know how to treat version != 1 (it does not exist yet)
    assert version == 1, version
    length = struct.unpack('B', binary[1])[0]
    authority = struct.unpack('>Q', '\x00\x00' + binary[2:8])[0]
    string = 'S-%d-%d' % (version, authority)
    binary = binary[8:]
    assert len(binary) == 4 * length
    for i in xrange(length):
        value = struct.unpack('<L', binary[4*i:4*(i+1)])[0]
        string += '-%d' % value
    return string