#!/bin/bash

HOST_ID=$1
INTERFACES=$2
WARNVAL=$3
CRITVAL=$4

LASTFILE=/tmp/${HOST_ID}-rx_errors
DIFVALS=(0)
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
    "for i in ${INTERFACES//,/ }; do ethtool -S \$i \
    | grep -e " rx_crc_errors" | awk '{print \$2}'; done" 2>/dev/null))

echo "${CURVALS[@]}"

if [ "$?" != "0" ] || [ -z "${CURVALS[1]}" ] ; then
    echo "UNKNOWN - Error executing check"
    echo "${CURVALS[@]}"
    exit 3
fi

if [ ! -f ${LASTFILE} ]; then
    echo "${CURVALS[@]}" > ${LASTFILE}
    echo "OK - First time execution. Recording current value."
    exit 0
fi

LASTVALS=($(cat ${LASTFILE}))
if [ "${#LASTVALS[@]}" != "${#CURVALS[@]}" ]; then
    echo "${CURVALS[@]}" > ${LASTFILE}
    echo "OK - Number of interfaces changed. Resetting value file"
    exit 0
fi

for i in $(seq ${#ifnames[@]}); do
    ival=$(expr ${CURVALS[$i]} - ${LASTVALS[$i]})
    DIFVALS[$i]=$ival
    if [ -n "${CRITVAL}" ] && [ "${ival}" -ge "${CRITVAL}" ]; then
        STATUS="CRITICAL"
        RETVAL=2
    elif [ -n "${WARNVAL}" ] && [ "${RETVAL}" -lt "1" ] && [ "${ival}" -ge "${WARNVAL}" ]; then
        STATUS="WARNING"
        RETVAL=1
    fi
done

echo "${CURVALS[@]}" > ${LASTFILE}

printf "%s |" ${STATUS}

for i in $(seq ${#ifnames[@]}); do
    ifindex=$(expr $i - 1)
    printf " %s_rx_errors=%d;%s;%s;;" ${ifnames[$ifindex]} \
        ${DIFVALS[$i]} ${WARNVAL} ${CRITVAL}
done
printf "\n"
exit ${RETVAL}