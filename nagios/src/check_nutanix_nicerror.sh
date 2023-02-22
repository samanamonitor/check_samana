#!/bin/bash

HOST_ID=$1
INTERFACES=$2
WARNVAL=$3
CRITVAL=$4

LASTFILE=/tmp/${HOST_ID}-rx_errors
DIFVALS=()
STATUS="OK"
RETVAL=0
inames=(${INTERFACES//,/ })

if ! grep -q ${HOST_ID} ~/.ssh/config; then
    echo "UNKNOWN - Host ${HOST_ID} not configured for ssh." >&2
    exit 3
fi

CURVALS=($(ssh ${HOST_ID} "for i in ${INTERFACES//,/ }; do ethtool -S \$i 2>/dev/null \
    | grep -e " rx_errors" | awk '{print \$2}'; done"))

if [ "$?" != "0" ] || [ -z "${CURVALS[0]}" ] ; then
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

for i in $(seq ${#CURVAL[@]}); do
    ival=$(expr ${CURVALS[i]} - ${LASTVALS[i]})
    DIFVALS[i]=$ival
    if [ -n "${CRITVAL}" ] && [ "${ival}" -ge "${CRITVAL}" ]; then
        STATUS="CRITICAL"
        RETVAL=2
    elif [ -n "${WARNVAL}" ] && [ "${RETVAL}" -lt "1" ] && [ "${ival}" -ge "${WARNVAL}" ]; then
        STATUS="WARNING"
        RETVAL=1
    fi
done

echo "${CURVALS[@]}" > ${LASTFILE}

printf "%s - |" ${STATUS}

for i in $(seq ${#DIFVAL[@]}); do
    printf " %s_rx_errors=%d;%s;%s;;" ${inames[i]} \
        ${DIFVAL[i]} ${WARNVAL} ${CRITVAL}
done
exit ${RETVAL}