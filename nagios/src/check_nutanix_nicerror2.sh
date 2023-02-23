#!/bin/bash

HOST_ID=$1
INTERFACES=$2
WARNVAL=$3
CRITVAL=$4

STATUS="OK"
RETVAL=0
ifnames=(${INTERFACES//,/ })
sshconfig=/home/nagios/.ssh/config
sshkey=/home/nagios/.ssh/id_rsa

if ! grep -q ${HOST_ID} ${sshconfig}; then
    echo "UNKNOWN - Host ${HOST_ID} not configured for ssh." >&2
    exit 3
fi

CURVALS=(0 $(ssh -F ${sshconfig} -i ${sshkey} ${HOST_ID} \
    "for i in ${INTERFACES//,/ }; do cat /sys/class/net/\$i/statistics/rx_errors; done" 2>/dev/null))

if [ "$?" != "0" ] || [ -z "${CURVALS[1]}" ] ; then
    echo "UNKNOWN - Error executing check"
    echo "${CURVALS[@]}"
    exit 3
fi

printf "OK |"

for i in $(seq ${#ifnames[@]}); do
    ifindex=$(expr $i - 1)
    printf " %s=%s;;;;" ${ifnames[$ifindex]} ${CURVALS[$i]}
done
printf "\n"
exit ${RETVAL}