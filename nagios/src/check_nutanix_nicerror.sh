#!/bin/bash

HOST_ID=$1
INTERFACE=$2
WARNVAL=$3
CRITVAL=$4

LASTFILE=/tmp/${HOST_ID}-${INTERFACE}
DIFVAL=""
STATUS="OK"

if ! grep -q ${HOST_ID} ~/.ssh/config; then
    echo "Host ${HOST_ID} not configured for ssh." >&2
    exit 1
fi

CURVAL=$(ssh ${HOST_ID} ethtool -S ${INTERFACE} \
    | grep -e " rx_errors" | awk '{print $2}')
if [ -f ${LASTFILE} ]; then
    LASTVAL=$(cat ${LASTFILE})
    DIFVAL=$(expr ${CURVAL} - ${LASTVAL})
fi

if [ -z "${DIFVAL}" ]; then
    echo "OK - First time execution. Recording current value."
    exit 0
fi

if [ -n "${CRITVAL}" ] && [ ${DIFVAL} -gt ${CRITVAL} ]; then
    printf "CRITICAL - Errors = %d | rx_errors=%d;%s;%s;;" \
        ${DIFVAL} ${DIFVAL} ${WARNVAL} ${CRITVAL}
    exit 2
elif [ -n "${WARNVAL}" ] && [ ${DIFVAL} -gt ${WARNVAL} ]; then
    printf "WARNING - Errors = %d | rx_errors=%d;%s;%s;;" \
        ${DIFVAL} ${DIFVAL} ${WARNVAL} ${CRITVAL}
    exit 1
fi
printf "OK - Errors = %d | rx_errors=%d;%s;%s;;" \
    ${DIFVAL} ${DIFVAL} ${WARNVAL} ${CRITVAL}
