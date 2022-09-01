#!/usr/bin/python3
from samana import citrixcloud
from samana import etcd
from samana.nagios import CheckUnknown, CheckWarning, CheckCritical, CheckResult
from urllib import parse
import sys, getopt
import traceback
import json

def usage(argv):
  usage = """Check WinRM v1.0.0
This nagios plugin come with ABSOLUTELY NO WARRANTY and is property of
SAMANA GROUP LLC. If you want to use it, you should contact us before
to get a license.
Copyright (c) 2019 Samana Group LLC

Usage:
  %s -i <customer ID> -u <client id> -p <client secret> [ -s ] | -e <etcd server and port x.x.x.x[:2379]> -d <site id> -t <ttl>

  -i <customer ID>      Customer ID collected from Citrix Cloud information
  -u <client id>        Citrix Cloud API client id
  -p <client secret>    Citrix Cloud API client secret
  -s                    Prints a list of available Sites with Ids available in Citrix Cloud
  -e <etcd>             Etcd server IP/Hostname and port(optional). Default port value is 2379
  -t <ttl>              Time(seconds) the records will expire in Etcd database. Default ttl is 300 seconds
  -d <site id>          Citrix Cloud Site Id
""" % argv[0]
  return usage

def get_sites(ctx):
    sites = ctx.get_sites()
    if len(sites) < 1:
        raise CheckUnknown("No sites configured for API client")
    addl = ''
    for s in sites:
        addl += "Site Name: %s, Site Id: %s\n" % (s['Name'], s['Id'])
    return CheckResult("Data Collected", addl=addl)

def get_site_data(ctx, site_id, ttl, etcdserver, etcdport):
    ctx.get_machines(site_id)
    etcdclient = etcd.Client(host=etcdserver, port=etcdport, protocol='http')
    etcdclient.put('samanamonitor/ctx_data/%s/farm' % (site_id), json.dumps(ctx.data['farm']), ttl)
    for dg_name in ctx.data['desktopgroup'].keys():
        etcdclient.put('samanamonitor/ctx_data/%s/desktopgroup/%s' % \
            (site_id, parse.quote(dg_name.lower())), json.dumps(ctx.data['desktopgroup'][dg_name]), ttl)
    for host_name in ctx.data['hosts'].keys():
        etcdclient.put('samanamonitor/ctx_data/%s/hosts/%s' % \
            (site_id, parse.quote(host_name.lower())), json.dumps(ctx.data['hosts'][host_name]), ttl)
        etcdclient.put('samanamonitor/ctx_data/%s/computer/%s/data' % \
            (site_id, parse.quote(host_name.lower())), json.dumps(ctx.data['hosts'][host_name]), ttl)
    return CheckResult("Data Collected %s" % site_id)

def main():
    customer_id = None
    client_id = None
    client_secret = None
    print_sites = False
    etcdserver = None
    etcdport = 2379
    site_id = None
    ttl = 300
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hsi:u:p:e:d:t:")

        for o, a in opts:
            if o == '-i':
                customer_id = a
            elif o == '-u':
                client_id = a
            elif o == '-p':
                client_secret = a
            elif o == '-s':
                print_sites = True
            elif o == '-e':
                temp = a.split(':')
                etcdserver = temp[0]
                if len(temp) > 1:
                    etcdport = temp[1]
            elif o == '-t':
                ttl = a
            elif o == '-d':
                site_id = a
            elif o == '-h':
                raise CheckUnknown(usage(sys.argv))
            else:
                raise CheckUnknown("Unknown argument %s" % o, addl=usage())

        if customer_id is None:
            raise CheckUnknown("Customer Id is Mandatory")
        if client_id is None:
            raise CheckUnknown("Client Id is Mandatory")
        if client_secret is None:
            raise CheckUnknown("Client Secret is Mandatory")
        if print_sites is False and site_id is None:
            raise CheckUnknown("Site Id is mandatory for collecting data.")
        if print_sites is False and etcdserver is None:
            raise CheckUnknown("Etcd server is mandatory for collecting data.")

        ctx = citrixcloud.Client(customer_id, client_id, client_secret)

        if print_sites:
            out = get_sites(ctx)
        else:
            out = get_site_data(ctx, site_id, ttl, etcdserver, etcdport)

    except CheckUnknown as e:
        out = e.result
    except CheckCritical as e:
        out = e.result
    except CheckWarning as e:
        out = e.result
    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        traceback_info = traceback.extract_tb(tb)
        out = CheckResult("Error: %s at line %s" % (str(e), tb.tb_lineno), addl=traceback_info.format, status=3, status_str="UNKNOWN")

    print(out)
    exit(out.status)

if __name__ == "__main__":
  main()

