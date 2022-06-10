#!/bin/bash

usage() {
    if [ -n "$1" ]; then
        echo "$1"
    fi
    echo "$0 -H <host id> -m <module> [ -c <critical value> -w <warning value> -E <etcd server>:<etcd port> ]"
    exit 3
}

unknown() {
    local MSG=$1
    echo "UNKNOWN - $MSG"
    return 3
}

get-cpu() {
    local JSON_DATA=$1
    local WARNING=$2
    local CRITICAL=$3
    CPU=($(echo $JSON_DATA | jq -r ".PercentIdleTime"))
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    IDLE=${CPU[0]}
    PERCUSED=$(( 100 - ${IDLE} ))
    PERFUSED="cpuLoad=${PERCUSED};${WARNING};${CRITICAL};0;100"
    if [ -n "${CRITICAL}" ] && [ ${PERCUSED} -gt ${CRITICAL} ]; then
        RET=2
        STATE="CRITICAL"
    elif [ -n "${WARNING}" ] && [ ${PERCUSED} -gt ${WARNING} ]; then
        RET=1
        STATE="WARNING"
    else
        RET=0
        STATE="OK"
    fi
    echo "${STATE} - CPU Usage ${PERCUSED}% | ${PERFUSED}"
    return $RET
}

get-ram() {
    local JSON_DATA=$1
    local WARNING=$2
    local CRITICAL=$3
    RAM=($(echo ${JSON_DATA} | \
        jq -r ".TotalVisibleMemorySize, .FreePhysicalMemory"))
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    TOTAL=$((${RAM[0]} / 1024))
    FREE=$((${RAM[1]} / 1024))
    USED=$(($TOTAL - $FREE))
    PERCUSED=$(( $USED * 100 / $TOTAL ))
    PERCFREE=$(( $FREE * 100 / $TOTAL ))
    PERFUSED="'Physical Memory Used'=${USED};;;0;${TOTAL} 'Physical Memory Utilization'=${PERCUSED};${WARNING};${CRITICAL};0;100"
    if [ -n "${CRITICAL}" ] && [ ${PERCUSED} -gt ${CRITICAL} ]; then
        RET=2
        STATE="CRITICAL"
    elif [ -n "${WARNING}" ] && [ ${PERCUSED} -gt ${WARNING} ]; then
        RET=1
        STATE="WARNING"
    else
        RET=0
        STATE="OK"
    fi
    echo "${STATE} - Physical Memory: Total: ${TOTAL}MB - Used: ${USED}MB (${PERCUSED}%) - Free ${FREE}MB (${PERCFREE}%) | ${PERFUSED}"
    return $RET
}

get-swap() {
    local JSON_DATA=$1
    local WARNING=$2
    local CRITICAL=$3
    SWAP=($(echo $JSON_DATA | \
        jq -r ".TotalSwapSpaceSize , .FreeSpaceInPagingFiles"))
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    TOTAL=$(( ${SWAP[0]} / 1024 ))
    FREE=$(( ${SWAP[1]} / 1024 ))
    USED=$(( ${TOTAL} - ${FREE} ))
    PERCUSED=$(( ${USED} * 100 / ${TOTAL} ))
    PERCFREE=$(( ${FREE} * 100 / ${TOTAL} ))
    PERFUSED="'Swap Memory Used'=${PERCUSED};${WARNING};${CRITICAL};0;100"
    if [ -n "${CRITICAL}" ] && [ ${PERCUSED} -gt ${CRITICAL} ]; then
        RET=2
        STATE="CRITICAL"
    elif [ -n "${WARNING}" ] && [ ${PERCUSED} -gt ${WARNING} ]; then
        RET=1
        STATE="WARNING"
    else
        RET=0
        STATE="OK"
    fi
    echo "${STATE} - Swap Memory: Total: ${TOTAL}MB - Used: ${USED}MB (${PERCUSED}%) - Free: ${FREE}MB (${PERCFREE}%) | ${PERFUSED}"
    return $RET
}

get-log() {
    local JSON_DATA=$1
    local LOGNAME=$2
    local WARNING=$3
    local CRITICAL=$4
    EVENTS=$(echo ${JSON_DATA} | \
        jq ".Events.[\"${LOGNAME}\"]")
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    if [ "$EVENTS" == "null" ]; then
        echo "UNKNOWN - Event '${LOGNAME}' log not found in server."
        return 3
    fi
    EVENT_COUNT=$(echo $EVENTS | jq 'length')
    if [ -n "${CRITICAL}" ] && [ ${EVENT_COUNT} -gt ${CRITICAL} ]; then
        RET=2
        STATE="CRITICAL"
    elif [ -n "${WARNING}" ] && [ ${EVENT_COUNT} -gt ${WARNING} ]; then
        RET=1
        STATE="WARNING"
    else
        RET=0
        STATE="OK"
    fi
    echo "${STATE} - Error or Warning Events=${EVENT_COUNT}"
    echo ${EVENTS} | jq -r ".[].Message[0:50]"
    return $RET
}

get-services() {
    local JSON_DATA=$1
    local INCLUDE=$2
    local EXCLUDE=$3
    local WARNING=$4
    local CRITICAL=$5

    q="[ .Services[] |
        select(.DisplayName + .ServiceName| test(\"${INCLUDE}\"; \"i\")) |
        select(.DisplayName + .ServiceName| test(\"${EXCLUDE}\";  \"i\")| not) | 
    { DisplayName: .DisplayName, ServiceName: .ServiceName, Status: .Status, State: .State } ]"
    ALLSERVICES=$(echo ${JSON_DATA} | jq "$q")
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    RUNNING=$(echo ${ALLSERVICES} | jq "[ .[] | select((.Status == 4) or (.State==\"Running\"))]")
    STOPPED=$(echo ${ALLSERVICES} | jq "[ .[] | select((.Status != 4) or ((.State!=null) and (.State!=\"Running\")))]")
    RUNNING_LEN=$(echo ${RUNNING} | jq "length")
    STOPPED_LEN=$(echo ${STOPPED} | jq "length")
    if [ -n "${CRITICAL}" ] && [ ${STOPPED_LEN} -gt ${CRITICAL} ]; then
        RET=2
        STATE="CRITICAL"
    elif [ -n "${WARNING}" ] && [ ${STOPPED_LEN} -gt ${WARNING} ]; then
        RET=1
        STATE="WARNING"
    else
        RET=0
        STATE="OK"
    fi
    echo "${STATE} - ${RUNNING_LEN} Services Running - ${STOPPED_LEN} Services Stopped"
    echo ${STOPPED} | jq -r ".[] | \"STOPPED - \" + .DisplayName + \" (\" + .ServiceName + \")\""
    return $RET
}

get-hddrives() {
    local JSON_DATA=$1
    local WARNING=$2
    local CRITICAL=$3
    local RET=0
    local STATE="OK"
    DISKS=$(echo ${JSON_DATA} | jq ".Disks")
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    if [ "${DISKS:0:1}" == "{" ]; then #one object
        DISKS=$(echo $DISKS | jq "[ . ]")
    fi
    q=".[] | .Name + \" \" + (.Size|tostring) + \" \" + \
        (.FreeSpace|tostring) + \" \" + \
        ((.Size - .FreeSpace)|tostring) + \" \" + \
        (((.Size - .FreeSpace) * 100 / .Size)|floor|tostring)"
    DISK_ARR=($(echo "$DISKS" | jq -r "$q"))
    PERFUSED=""
    MSG=""
    ADDLMSG=""
    while [ -n "${DISK_ARR[0]}" ] ; do
        NAME=${DISK_ARR[0]}
        TOTAL=$((${DISK_ARR[1]} / 1048576 ))  # / 1073741824))
        FREE=$((${DISK_ARR[2]} / 1048576)) # / 1073741824))
        USED=$((${DISK_ARR[3]} / 1048576)) # / 1073741824))
        PERCUSED=${DISK_ARR[4]}
        PERFUSED="$PERFUSED $NAME=$PERCUSED;${WARNING};${CRITICAL};0;100"
        DISK_ARR=("${DISK_ARR[@]:5}")
        if [ -n "${CRITICAL}" ] && [ ${PERCUSED} -gt ${CRITICAL} ]; then
            MSG="$MSG CRIT:${NAME}=${PERCUSED}%"
            RET=2
            STATE="CRITICAL"
        elif [ -n "${WARNING}" ] && [ ${PERCUSED} -gt ${WARNING} ]; then
            MSG="$MSG WARN:${NAME}=${PERCUSED}%"
            if [ "$RET" -lt "1" ]; then
                RET=1
                STATE="WARNING"
            fi
        fi
        ADDLMSG="${ADDLMSG}Disk ${NAME} Total: ${TOTAL}MB - Used: ${USED}MB (${PERCUSED}%)\n"
    done
    if [ -z "$MSG" ]; then
        MSG="Disks usage is normal."
    fi
    echo "${STATE} - $MSG | $PERFUSED"
    echo -e "${ADDLMSG}"
    return $RET
}

get-uptime() {
    local JSON_DATA=$1
    local WARNING=$2
    local CRITICAL=$3
    UPTIME=$(echo $JSON_DATA | jq ".UpTime | floor")
    if [ "$?" != "0" ]; then
        echo -e "UNKNOWN - Invalid Data:\n${JSON_DATA}"
        return 3
    fi
    if [ -n "${CRITICAL}" ] && [ ${UPTIME} -gt ${CRITICAL} ]; then
        RET=2
        STATE="CRITICAL"
    elif [ -n "${WARNING}" ] && [ ${UPTIME} -gt ${WARNING} ]; then
        RET=1
        STATE="WARNING"
    else
        RET=0
        STATE="OK"
    fi
    PERF="uptime=${UPTIME};${WARNING};${CRITICAL};;"
    echo "${STATE} - Uptime of server is ${UPTIME} Hours | ${PERF}"
    return $RET
}

while getopts ":hc:w:E:H:m:s:i:e:" opt; do
    case ${opt} in
        h )
        usage
        ;;
        H )
        HOSTID=${OPTARG}
        ;;
        E )
        ETCDSERVER=${OPTARG}
        ;;
        c )
        CRITICAL=${OPTARG}
        ;;
        w )
        WARNING=${OPTARG}
        ;;
        m )
        MODULE=${OPTARG}
        ;;
        s )
        SUBMODULE=${OPTARG}
        ;;
        i )
        INCLUDE=${OPTARG}
        ;;
        e )
        EXCLUDE=${OPTARG}
        ;;
        : )
        usage
        ;;
    esac
done
if [ -z ${HOSTID} ]; then
    usage "Invalid Host id"
fi
[[ ${ETCDSERVER} == *":"* ]] || \
    usage "Invalid Etcd Server. Format <host>:<port>"

if [ -z ${ETCDSERVER} ]; then
    ETCDSERVER="localhost:2379"
fi

KEY=/samanamonitor/data/${HOSTID}
ENDPOINT="http://${ETCDSERVER}"

JSON_DATA=$(etcdctl --endpoint ${ENDPOINT} get ${KEY} 2>&1)
if [ "$?" != "0" ]; then
    echo "UNKNOWN - $JSON_DATA"
    exit 3
fi

case ${MODULE} in
    cpu )
        get-cpu "${JSON_DATA}" ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    ram )
        get-ram "${JSON_DATA}" ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    swap )
        get-swap "${JSON_DATA}" ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    log )
        if [ -z "${SUBMODULE}" ]; then
            usage "Log name not defined. Use -s <log name>"
        fi
        get-log "${JSON_DATA}" ${SUBMODULE} ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    services )
        get-services "${JSON_DATA}" "${INCLUDE}" "${EXCLUDE}" ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    hddrives )
        get-hddrives "${JSON_DATA}" ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    uptime )
        get-uptime "${JSON_DATA}" ${WARNING} ${CRITICAL}
        ret=$?
        ;;
    * )
        usage "Invalid module"
        ;;
esac
exit $ret
