#!/usr/bin/python

from sys import argv
from pynag import Model

if len(argv) != 3:
  print "ERROR - invalid parameter"
  print "usage: %s <Service Description> <host name>" % argv[0]
  exit(1)
#sd = "Citrix Provisioning Services"
sd = argv[1]
#hn = "TRVPVSP002"
hn = argv[2]

print Model.Service.objects.filter(service_description=sd)[0].get_effective_command_line(host_name=hn)

