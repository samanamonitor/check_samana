#!/usr/bin/python

import json
from itertools import izip

ldap_server='ldap://snv.net'
username = "xd931@snv.net"
password = "C.aes3dsT6zZ"
basedn='dc=snv,dc=net'

def application(environ, start_fn):
    indata=environ['PATH_INFO'].split('/')
    if len(indata) > 1:
        func=indata[1]
    else:
        func=''
    if len(indata) > 2:
        search_data=indata[2]
        if len(search_data.split('-')) == 8:
            user_sid = search_data
        else:
            user_sid = get_user_sid(search_data)
        if user_sid is None:
            start_fn('400 INVALID USER SID', [('Content-Type', 'text/plain')])
            return ["Invalid function %s\n" % func]
    else:
        search_data=None


    if func == 'userdata':
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps({'username': search_data, 'sid': user_sid})]
    elif func == 'listusers':
        user_list = get_user_list()
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps(user_list)]
    elif func == "xml":
        xmldata = get_user_xmldata(user_sid)
        if xmldata is None:
            start_fn('400 INVALID USER SID', [('Content-Type', 'text/plain')])
            return ["Invalid user %s\n" % search_data]
        start_fn('200 OK', [('Content-Type', 'application/xml')])
        return [ str(xmldata) ]
    elif func == "printers":
        xmldata = get_user_xmldata(user_sid)
        if xmldata is None:
            start_fn('400 INVALID XML DATA', [('Content-Type', 'text/plain')])
            return ["Invalid XML data for %s\n" % search_data]
        printers = get_printers(str(xmldata))
        if printers is None:
            start_fn('400 INVALID PRINTER DATA', [('Content-Type', 'text/plain')])
            return ["Invalid printer data for %s\n" % search_data]
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [ json.dumps(printers) ]
    elif func == "drives":
        xmldata = get_user_xmldata(user_sid)
        if xmldata is None:
            start_fn('400 INVALID XML DATA', [('Content-Type', 'text/plain')])
            return ["Invalid XML data for %s\n" % search_data]
        drives = get_drives(str(xmldata))
        if drives is None:
            start_fn('400 INVALID DRIVE DATA', [('Content-Type', 'text/plain')])
            return ["Invalid drive data for %s\n" % search_data]
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [ json.dumps(drives) ]
    elif func == "icons":
        xmldata = get_user_xmldata(user_sid)
        if xmldata is None:
            start_fn('400 INVALID XML DATA', [('Content-Type', 'text/plain')])
            return ["Invalid XML data for %s\n" % search_data]
        icons = get_icons(str(xmldata))
        if icons is None:
            start_fn('400 INVALID ICON DATA', [('Content-Type', 'text/plain')])
            return ["Invalid icon data for %s\n" % search_data]
        start_fn('200 OK', [('Content-Type', 'application/json')])
        return [ json.dumps(icons) ]
    else:
        start_fn('400 INVALID FUNC', [('Content-Type', 'text/plain')])
        return ["Invalid function %s\n" % func]

def pairwise(iterable):
    "s -> (s0, s1), (s2, s3), (s4, s5), ..."
    a = iter(iterable)
    return izip(a, a)

def xml_2_hash(property_list):
    out = {}
    for p in property_list:
        out[p.attrib['Name']] = p.text
    return out

def get_user_list():
    import etcd
    client = etcd.Client(port=2379)
    try:
        sid_list = []
        etcd_sid_list = client.get('/pre-onboarding').children
        for item in etcd_sid_list:
            sid_list.append(item.key.split('/')[-1])
    except etcd.EtcdKeyNotFound:
        print "No users found"
        return None
    return get_users_samaccountname(sid_list)

def get_printers(xmltxt):
    import xml.etree.ElementTree as et
    root = et.fromstring(xmltxt)
    if root[0].attrib['Type'] != "System.Collections.Hashtable":
        print "Invalid XML"
        return None
    printers = []
    for k,v in pairwise(root[0]):
        if k.text == "printers" and v.attrib['Type'] == "System.Object[]":
            for printer in v:
                printers.append( xml_2_hash(printer))
            break
    return printers

def get_drives(xmltxt):
    import xml.etree.ElementTree as et
    root = et.fromstring(xmltxt)
    if root[0].attrib['Type'] != "System.Collections.Hashtable":
        print "Invalid XML"
        return None
    drives = []
    for k,v in pairwise(root[0]):
        if k.text == "drives" and v.attrib['Type'] == "System.Object[]":
            for drive in v:
                drives.append(xml_2_hash(drive))
            break
        else:
            drives.append(xml_2_hash(v))
    return drives

def get_icons(xmltxt):
    import xml.etree.ElementTree as et
    root = et.fromstring(xmltxt)
    if root[0].attrib['Type'] != "System.Collections.Hashtable":
        print "Invalid XML"
        return None
    icons = []
    for k,v in pairwise(root[0]):
        if k.text == "icons" and v.attrib['Type'] == "System.Object[]":
            for icon in v:
                icons.append(icon.text[:-4])
            break
    return icons

def get_user_xmldata(objectSid):
    import etcd
    client = etcd.Client(port=2379)
    try:
        data_b64 = client.get('/pre-onboarding/%s' % objectSid).value
    except etcd.EtcdKeyNotFound:
        print "User not found"
        return None
    import base64
    data = base64.b64decode(data_b64)
    return data.decode("UTF-16").encode("UTF-8")

def get_user_sid(samaccountname):
    import ldap
    l = ldap.initialize(ldap_server)
    l.protocol_version = ldap.VERSION3
    l.simple_bind_s(username, password)
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

def get_users_samaccountname(sid_list):
    import ldap
    l = ldap.initialize(ldap_server)
    l.protocol_version = ldap.VERSION3
    l.simple_bind_s(username, password)
    searchFilter="(|" + ''.join(map(lambda x:"(objectSid=%s)" % x, sid_list)) + ")"
    searchAttribute=["objectSid", "SamAccountName"]
    searchScope=ldap.SCOPE_SUBTREE
    search_id = l.search(basedn, searchScope, searchFilter, searchAttribute)
    user_data = []
    while True:
        search_result = l.result(search_id, 0)
        if search_result[0] != 100: break
        user_data.append({'samaccountname': search_result[1][0][1]['sAMAccountName'][0], 
            'sid': convert_sid_bin_txt(search_result[1][0][1]['objectSid'][0])})
    return user_data

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