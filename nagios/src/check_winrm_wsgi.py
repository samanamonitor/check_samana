#!/usr/bin/python

import urllib2
import json
import sys
import getopt
import urllib

def main():
  query = {}
  try:
    opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:n:s:w:c:U:A:")

    for o, a in opts:
      if o == '-H':
        query["hostaddress"] = a
      elif o == '-d':
        query["u_domain"] = a 
      elif o == '-u':
        query["username"] = a
      elif o == '-p':
        query["password"] = a
      elif o == '-a':
        query["authfile"] = a
      elif o == '-n':
        query["nagiosaddress"] = a
      elif o == '-s':
        query["script"] = a
      elif o == '-w':
        query["warning"] = a
      elif o == '-c':
        query["critical"] = a
      elif o == '-U':
        query["url"] = a
      elif o == '-A':
        query["scriptarguments"] = a
      elif o == '-h':
        raise Exception("Unknown argument")

    f = urllib2.urlopen("http://localhost/check_winrm?%s" % urllib.encode('&'.join(query)))

    resp = json.load(f)

    print resp['message']
    exit(resp['status'])


  except Exception as err:
    exc_type, exc_obj, tb = sys.exc_info()
    print "UNKNOWN - main Error: %s at line %s" % \
      (str(err), tb.tb_lineno)
    exit(3)

if __name__ == "__main__":
  main()