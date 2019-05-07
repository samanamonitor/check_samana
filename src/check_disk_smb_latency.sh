#!/bin/sh

echo $0 $@ >> /tmp/latency.txt
/usr/local/nagios/libexec/check_disk_smb_latency $@
exit $?
