#!/bin/bash

from pynag.Model import Service
from sys import argv

def usage(argv):
    print("Usage: %s <service description> <host name> <role to be added>" % argv[0])
    exit(1)

if len(argv) != 4:
    usage()

service_description=argv[1]
host_name=argv[2]
append_role=argv[3]

srv_list = Service.objects.filter(service_description=service_description, host_name=host_name)
if len(srv_list) < 1:
    print("Unable to find service %s at host %s" % (service_description, host_name))

srv = srv_list[0]
srv.attribute_appendfield(attribute_name="use", value=append_role)
srv.save()