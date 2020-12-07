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
        start_fn('200 OK', [('Content-Type', 'application/xml')])
        user_sid = get_user_sid(username)
        return [get_user_xmldata(user_sid)]
        #return [json.dumps({'username': username, 'sid': user_sid, 'xml': get_user_xmldata(user_sid)})]
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