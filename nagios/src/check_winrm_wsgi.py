#!/usr/bin/python

import urllib2
import json

def main():
  query = []
  try:
    opts, args = getopt.getopt(sys.argv[1:], "H:d:u:p:ha:n:s:w:c:U:A:")

    for o, a in opts:
      if o == '-H':
        query += [ "hostaddress=%s" % a ]
      elif o == '-d':
        query += [ "u_domain=%s" % a ]
      elif o == '-u':
        query += [ "username=%s" % a ]
      elif o == '-p':
        query += [ "password=%s" % a ]
      elif o == '-a':
        query += [ "authfile=%s" % a ]
      elif o == '-n':
        query += [ "nagiosaddress=%s" % a ]
      elif o == '-s':
        query += [ "script=%s" % a ]
      elif o == '-w':
        query += [ "warning=%s" % a ]
      elif o == '-c':
        query += [ "critical=%s" % a ]
      elif o == '-U':
        query += [ "url=%s" % a ]
      elif o == '-A':
        query += [ "scriptarguments=%s" % a ]
      elif o == '-h':
        raise Exception("Unknown argument")

    f = urllib2.urlopen("http://localhost/check_winrm?%s" % '&'.join(query))

    resp = json.load(f)

    print resp.message
    exit(resp.status)


  except Exception as err:
    exc_type, exc_obj, tb = sys.exc_info()
    print "UNKNOWN - main Error: %s at line %s" % \
      (str(err), tb.tb_lineno)
    exit(3)

if __name__ == "__main__":
  main()