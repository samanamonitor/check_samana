#!/usr/bin/python

from pynag.Model import Service
from sys import argv

def usage(argv):
    print("Usage: %s <service description> <host name> <attribute name> <value to be added>" % argv[0])
    exit(1)

if len(argv) != 5:
    usage(argv)

service_description=argv[1]
host_name=argv[2]
attribute_name=argv[3]
value=argv[4]

srv_list = Service.objects.filter(service_description=service_description, host_name=host_name)
if len(srv_list) < 1:
    print("Unable to find service %s at host %s" % (service_description, host_name))

srv = srv_list[0]
srv.set_attribute(attribute_name=attribute_name, attribute_value=value)
srv.save()