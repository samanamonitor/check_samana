#!/usr/bin/python3
import citrixcloud
import samanaetcd as etcd
import sys, getopt
import json

class CheckCtxCloudWarning(Exception):
    pass

class CheckCtxCloudError(Exception):
    pass

class CheckCtxCloudUnknown(Exception):
    pass


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
"""
  print(usage)


def main(argv):
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
                usage(args)
            else:
                raise Exception("Unknown argument")

        if customer_id is None:
            raise CheckCtxCloudUnknown("Customer Id is Mandatory")
        if client_id is None:
            raise CheckCtxCloudUnknown("Client Id is Mandatory")
        if client_secret is None:
            raise CheckCtxCloudUnknown("Client Secret is Mandatory")

        ctx = citrixcloud.Client(customer_id, client_id, client_secret)

        if print_sites:
            sites = ctx.get_sites()
            if len(sites) < 1:
                raise CheckCtxCloudUnknown("No sites configured for API client")

            print("OK - Data Collected")
            for s in sites:
                print("Site Name: %s, Site Id: %s" % (s['Name'], s['Id']))
            exit(0)

        if site_id is None:
            raise CheckCtxCloudUnknown("Site Id is mandatory for collecting data.")
        if etcdserver is None:
            raise CheckCtxCloudUnknown("Etcd server is mandatory for collecting data.")

        etcdclient = etcd.Client(host=etcdserver, port=etcdport, protocol='http')
        ctx.get_machines(site_id)
        etcdclient.put('/samanamonitor/ctx_data/%s/farm' % (site_id), json.dumps(ctx.data['farm']), ttl)
        for dg_name in ctx.data['desktopgroup'].keys():
            etcdclient.put('/samanamonitor/ctx_data/%s/desktopgroup/%s' % \
                (site_id, dg_name.lower()), json.dumps(ctx.data['desktopgroup'][dg_name]), ttl)
        for host_name in ctx.data['hosts'].keys():
            etcdclient.put('samanamonitor/ctx_data/%s/hosts/%s' % \
                (site_id, host_name.lower()), json.dumps(ctx.data['hosts'][host_name]), ttl)

    except CheckCtxCloudUnknown as err:
        print("UNKNOWN - %s" % (str(err)))
        exit(3)
    except CheckCtxCloudError as err:
        print("ERROR - %s" % (str(err)))
        exit(2)
    except CheckCtxCloudWarning as err:
        print("WARNING - %s" % (str(err)))
        exit(1)
    except Exception as err:
        exc_type, exc_obj, tb = sys.exc_info()
        print("UNKNOWN - main Error: %s at line %s" % \
            (str(err), tb.tb_lineno))
        exit(3)

    print("OK - Data Collected")

if __name__ == "__main__":
  main(sys.argv)


