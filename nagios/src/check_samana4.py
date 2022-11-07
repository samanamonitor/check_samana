#!/usr/bin/python3

import sys
sys.path.append('/usr/local/nagios/libexec/lib/python3/dist-packages')
from sammcheck import SAMMEtcdCheck

if __name__ == "__main__":
    check = SAMMEtcdCheck(sys.argv[1:])
    check.run()
    print(check)
    exit(check.outval)
