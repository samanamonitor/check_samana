#!/bin/bash

HOST_ID=$1
INTERFACE=$2
WARNVAL=$3
CRITVAL=$4

LASTFILE=/tmp/${HOST_ID}-${INTERFACE}
DIFVAL=""
STATUS="OK"
RETVAL=0

if ! grep -q ${HOST_ID} ~/.ssh/config; then
    echo "UNKNOWN - Host ${HOST_ID} not configured for ssh." >&2
    exit 3
fi

CURVAL=$(ssh ${HOST_ID} ethtool -S ${INTERFACE} 2>/dev/null \
    | grep -e " rx_errors" | awk '{print $2}')

if [ "$?" != "0" ] || [ -z ${CURVAL} ] ; then
    echo "UNKNOWN - Error executing check"
    echo ${CURVAL}
    exit 3
fi

if [ -f ${LASTFILE} ]; then
    LASTVAL=$(cat ${LASTFILE})
    DIFVAL=$(expr ${CURVAL} - ${LASTVAL})
fi

echo "${CURVAL}" > ${LASTFILE}

if [ -z "${DIFVAL}" ]; then
    echo "OK - First time execution. Recording current value."
    exit 0
fi

if [ -n "${CRITVAL}" ] && [ ${DIFVAL} -ge ${CRITVAL} ]; then
    STATUS="CRITICAL"
    RETVAL=2
elif [ -n "${WARNVAL}" ] && [ ${DIFVAL} -ge ${WARNVAL} ]; then
    STATUS="WARNING"
    RETVAL=1
fi

printf "%s - Errors = %d | rx_errors=%d;%s;%s;;\n" ${STATUS} \
    ${DIFVAL} ${DIFVAL} ${WARNVAL} ${CRITVAL}
exit ${RETVAL}