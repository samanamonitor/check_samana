#!/usr/bin/python

import json
from itertools import izip
import traceback
import sys

ldap_server='ldap://snv.net'
username = "xd931@snv.net"
password = "C.aes3dsT6zZ"
basedn='dc=snv,dc=net'

installed_apps = {
    "Accessibility\\",
    "Accessories\\",
    "Administrative Tools\\",
    "Check Point\\Check Point Endpoint Security VPN",
    "Cisco\\Cisco AnyConnect Secure Mobility Client\\Cisco AnyConnect Diagnostics and Reporting Tool",
    "Cisco\\Cisco AnyConnect Secure Mobility Client\\Cisco AnyConnect Secure Mobility Client",
    "Cisco Webex Meetings\\Cisco Webex Meetings",
    "Cisco Webex Meetings Desktop App\\Uninstall",
    "Cisco Webex Productivity Tools\\Check for Updates...",
    "Cisco Webex Productivity Tools\\Help",
    "Cisco Webex Productivity Tools\\Preferences",
    "Cisco Webex Productivity Tools\\Send Problem Report",
    "Cisco Webex Productivity Tools\\Uninstall",
    "LenderWorkbench\\LenderWorkBench Production",
    "McAfee\\McAfee Endpoint Security",
    "Microsoft Endpoint Manager\\Configuration Manager\\Software Center",
    "Microsoft Office Tools\\Database Compare",
    "Microsoft Office Tools\\Office Language Preferences",
    "Microsoft Office Tools\\Office Upload Center",
    "Microsoft Office Tools\\Skype for Business Recording Manager",
    "Microsoft Office Tools\\Spreadsheet Compare",
    "Microsoft Office Tools\\Telemetry Dashboard for Office",
    "Microsoft Office Tools\\Telemetry Log for Office",
    "StartUp\\Skype for Business 2016",
    "Synergy ECM\\Synergy Desktop Manager",
    "System Tools\\",
    "Windows PowerShell\\",
    "Acrobat Reader DC",
    "Adobe Acrobat DC",
    "Citrix Workspace",
    "Excel",
    "Google Chrome",
    "OneNote 2016",
    "Outlook",
    "PowerPoint",
    "Publisher",
    "Skype for Business",
    "Word",
}

def application(environ, start_fn):
    indata=environ['PATH_INFO'].split('/')

    try:
        try:
            func = indata[1]
        except IndexError:
            raise IndexError('400 INVALID FUNC', "Invalid Function %s" % func)
        params = indata[2:]
        output = [ "UNKNOWN" ]

        if func == 'userdata':
            output = get_userdata(params, output="wsgi")
            start_fn('200 OK', [('Content-Type', 'application/json')])
        elif func == 'listusers':
            output = get_listusers(output="wsgi")
            start_fn('200 OK', [('Content-Type', 'application/json')])
        elif func == "xml":
            output = get_xml(params)
            start_fn('200 OK', [('Content-Type', 'application/xml')])
        elif func == "printers":
            output = get_printers(params, output="wsgi")
            start_fn('200 OK', [('Content-Type', 'application/json')])
        elif func == "drives":
            start_fn('200 OK', [('Content-Type', 'application/json')])
            output = get_drives(params, output="wsgi")
        elif func == "icons":
            output = get_icons(params, output="wsgi")
            start_fn('200 OK', [('Content-Type', 'application/json')])
        elif func == "csv":
            output = get_csv(params)
            start_fn('200 OK', [('Content-Type', 'text/csv'), 
                ("Content-Disposition", "attachment;filename=preonboarding.csv")])
        elif func == "csvall":
            output = get_csvall()
            start_fn('200 OK', [('Content-Type', 'text/csv'), 
                ("Content-Disposition", "attachment;filename=preonboarding.csv")])
        else:
            raise Exception('400 INVALID FUNC', "Invalid function %s\n" % func)

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        try:
            start_fn(e[0], [('Content-Type', 'text/plain')])
            return e[1]
        except:
            start_fn("400 UNKNOWN", [('Content-Type', 'text/plain')])
            return [ "UNKNOWN" ]


    return output


def pairwise(iterable):
    "s -> (s0, s1), (s2, s3), (s4, s5), ..."
    a = iter(iterable)
    return izip(a, a)

def xml_2_hash(property_list):
    out = {}
    for p in property_list:
        out[p.attrib['Name']] = p.text
    return out

def get_sid_list(search_data_list):
    sid_list = []

    for i in search_data_list:
        sid_list.append(get_user_sid(i))

    if len(sid_list) == 0:
        raise IndexError('400 INVALID USER SID', "Invalid user data %s\n" % str(search_data_list))
    return sid_list

def filter_icons(icon_list, filter_out):
    out = []
    for icon in icon_list:
        found = False
        for i in installed_apps:
            if icon.startswith(i):
                found = True
                break
        if found: continue
        out.append(icon)
    return out

def get_param_user_list(params):
    try:
        user_list = params[0]
    except IndexError:
        raise IndexError('400 INVALID USER SID', "Invalid user data %s\n" % user_list)
    return user_list.split(',') 

def get_userdata(params=None, sid_list=None):
    if sid_list == None:
        sid_list = get_sid_list(get_param_user_list(params))

    return [json.dumps(map(lambda un, sid: {'username': un, 'sid': sid}), search_data_list, user_sid )]

def get_listusers(output="array"):
    import etcd
    client = etcd.Client(port=2379)
    try:
        sid_list = []
        etcd_sid_list = client.get('/pre-onboarding').children
        for item in etcd_sid_list:
            sid_list.append(item.key.split('/')[-1].encode("ascii"))
    except etcd.EtcdKeyNotFound:
        raise etcd.EtcdKeyNotFound('400 NO USERS FOUND', "No users found")

    if output == "array":
        return sid_list
    if output == "wsgi":
        return [json.dumps(get_users_samaccountname(sid_list))]

def get_xml(params=None, sid_list=None):
    if sid_list is None:
        sid_list = get_sid_list(get_param_user_list(params))

    xmldata = get_user_xmldata(sid_list[0])

    return [ str(xmldata) ]

def get_printers(params=None, sid_list=None, output="array"):
    if sid_list is None:
        sid_list = get_sid_list(get_param_user_list(params))

    import xml.etree.ElementTree as et

    printers = []
    for sid in sid_list:
        xmltxt = get_user_xmldata(sid)
        root = et.fromstring(xmltxt)
        if root[0].attrib['Type'] != "System.Collections.Hashtable":
            raise Exception('400 INVALID XML', "Invalid xml text: %s" % xmltxt)
        for k,v in pairwise(root[0]):
            if k.text == "printers" and v.attrib['Type'] == "System.Object[]":
                for printer in v:
                    printers.append( xml_2_hash(printer))
                break

    if output == "array":
        return printers
    elif output == "wsgi":
        return [ json.dumps(printers) ]
    
def get_drives(params=None, sid_list=None, output="array"):
    if sid_list is None:
        sid_list = get_sid_list(get_param_user_list(params))

    import xml.etree.ElementTree as et

    drives = []
    for sid in sid_list:
        xmltxt = get_user_xmldata(sid)
        root = et.fromstring(xmltxt)
        if root[0].attrib['Type'] != "System.Collections.Hashtable":
            raise Exception('400 INVALID XML', "Invalid xml text: %s" % xmltxt)

        for k,v in pairwise(root[0]):
            if k.text == "drives" and v.attrib['Type'] == "System.Object[]":
                for drive in v:
                    drives.append(xml_2_hash(drive))
                break
            elif k.text == "drives":
                print v.attrib['Type']
                drives.append(xml_2_hash(v))

    if output == "array":
        return drives
    elif output == "wsgi":
        return [ json.dumps(drives) ]

def get_icons(params=None, sid_list=None, output="array"):
    if sid_list is None:
        sid_list = get_sid_list(get_param_user_list(params))

    import xml.etree.ElementTree as et

    icons = []
    for sid in sid_list:
        xmltxt = get_user_xmldata(sid)
        root = et.fromstring(xmltxt)
        if root[0].attrib['Type'] != "System.Collections.Hashtable":
            raise Exception('400 INVALID XML', "Invalid xml text: %s" % xmltxt)

        for k,v in pairwise(root[0]):
            if k.text == "icons" and v.attrib['Type'] == "System.Object[]":
                icons = filter_icons([icon.text[:-4] for icon in v], installed_apps)
                break
    if output == "array":
        return icons
    elif output == "wsgi":
        return [ json.dumps(icons) ]

def get_csv(params=None, sid_list=None):
    if sid_list is None:
        sid_list = get_sid_list(get_param_user_list(params))

    from StringIO import StringIO
    import xml.etree.ElementTree as et
    import csv

    csv_io = StringIO()
    csv_wr = csv.writer(csv_io)

    csv_wr.writerow(["User", "Type", "Icon", "Drive Letter", "UNC", "Printer Name", "Port/Share Name"])

    users = get_users_samaccountname(sid_list)
    for user in users:
        csv_wr.writerows(get_user_array(user))

    return [ csv_io.getvalue() ]

def get_csvall():
    sid_list = get_listusers()
    return get_csv(sid_list=sid_list)

def get_user_array(user):
    out = []
    icons = get_icons(sid_list=[user['sid']])
    for icon in icons:
        out.append([user['samaccountname'], "icon", icon, "", "", "", ""])

    drives = get_drives(sid_list=[user['sid']])
    for drive in drives:
        if ''
        if 'LocalPath' not in drive:
            out.append([user['samaccountname'], "drive", "", "old version - rerun script on local PC", "", "", ""])
            continue
        out.append([user['samaccountname'], "drive", "", drive['LocalPath'], drive['RemotePath'], "", ""])

    printers = get_printers(sid_list=[user['sid']])
    for printer in printers:
        printer_data = printer.get('ShareName', "")
        if printer_data is None or printer_data == "":
            printer_data = printer.get('PortName', "")
        if printer_data is None or printer_data == "":
            printer_data = "--"
        out.append([user['samaccountname'], "printer", "", "", "", printer['Name'], printer_data])
    return out

def get_user_xmldata(objectSid):
    import etcd
    client = etcd.Client(port=2379)
    try:
        data_b64 = client.get('/pre-onboarding/%s' % objectSid).value
    except etcd.EtcdKeyNotFound:
        raise etcd.EtcdKeyNotFound("400 USER NOT FOUND", "User data not in store")

    import base64
    data = base64.b64decode(data_b64)
    return data.decode("UTF-16").encode("ascii", 'ignore')

def get_user_sid(data):
    if len(data.split('-')) == 8:
        return data

    import ldap
    try:
        l = ldap.initialize(ldap_server)
        l.protocol_version = ldap.VERSION3
        l.simple_bind_s(username, password)
        searchFilter="(samAccountName=%s)" % data
        searchAttribute=["objectSid"]
        searchScope=ldap.SCOPE_SUBTREE
        search_id = l.search(basedn, searchScope, searchFilter, searchAttribute)
        search_result = l.result(search_id, 0)
        objectSid = search_result[1][0][1]['objectSid'][0]
    except IndexError:
        raise IndexError('400 Invalid LDAP result', "IndexError: Invalid LDAP result searchFilter=%s")
    except TypeError:
        raise TypeError('400 Invalid LDAP result', "TypeError: Invalid LDAP result searchFilter=%s")

    return convert_sid_bin_txt(objectSid)

def get_users_samaccountname(sid_list):
    import ldap
    try:
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
    except Exception as e:
        raise Exception('400 NO SAMACCOUNTNAME', "Unable to get sAMAccountName from %s" % str(sid_list))
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