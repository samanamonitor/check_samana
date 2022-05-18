#!/bin/bash

if [ -n "$SAMANA_DEBUG" ]; then
    set -x
fi

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
#IMAGE_NAME=$1
#USERNAME=$2
#PASSWORD=$3
#DOMAIN=$4
#WMISERVER=$5
#ETCDSERVER=$6
#ETCDPORT="2379"
CONTAINER_NAME=test

finish_test() {
    LOG_CONT=$(docker stop ${CONTAINER_NAME} 2>&1)
    out=$?
    if [ "$?" != "0" ]; then
        echo "Error stopping container($CONTAINER_NAME)."
        echo $LOG_CONT
    fi
    echo "Test finished."
    exit $out
}

check_var() {
    varname=$1
    eval v='$'$varname
    if [ -z "$v" ]; then
        echo "Undefined $varname variable. Cannot continue."
        exit 1
    fi
}

check_var IMAGE_NAME
check_var USERNAME
check_var PASSWORD
check_var DOMAIN
check_var WMISERVER
check_var ETCDSERVER
check_var ETCDPORT

echo "Creating container ${CONTAINER_NAME}"
LOG_CONT=$(docker create -it --rm --name ${CONTAINER_NAME} --mount type=bind,source=${DIR},destination=/opt/samana ${IMAGE_NAME} 2>&1)
out=$?
if [ "$out" != "0" ]; then
    echo "Error creating the container."
    echo $LOG_CONT
    exit $out
fi
echo "Container(${CONTAINER_NAME}) created succesfully."
echo "Starting container($CONTAINER_NAME)."
LOG_CONT=$(docker start ${CONTAINER_NAME} 2>&1)
out=$?
if [ "$?" != "0" ]; then
    echo "Error starting container."
    echo $LOG_CONT
    exit $out
fi
CONT_IP=$(docker inspect test | jq -r .[0].NetworkSettings.Networks.bridge.IPAddress 2>&1)
out=$?
if [ "$?" != "0" ]; then
    echo "Unable to get IP address of the container"
    echo $CONT_IP
    finish_test
    exit $out
fi
echo "Container(${CONTAINER_NAME}) started successfully."
sleep 5
q=$(sed -e "s/%USERNAME%/$USERNAME/" \
        -e "s/%PASSWORD%/$PASSWORD/" \
        -e "s/%DOMAIN%/$DOMAIN/" \
        -e "s/%WMISERVER%/$WMISERVER/" \
        -e "s/%ETCDSERVER%/$ETCDSERVER/" \
        -e "s/%ETCDPORT%/$ETCDPORT/" ${DIR}/query-test.json)
echo "Sending Query to container."
res=$(curl -s -d "$q" http://${CONT_IP}/wmi 2>&1)
out=$?
if [ "$out" != "0" ]; then
    echo "Error sending query."
    echo $res
    finish_test
    exit $out
fi
status=$(echo $res | jq -r .status)
if [ "$status" != "0" ]; then
    echo "Error completing the query"
    echo $res | jq -r .info1
    finish_test
    exit $status
fi
id=$(echo $res | jq -r .info1 | sed -e "s/.*ID=//")
echo "Data was sent succesfully to the ETCD server"
echo "Collecting data saved in ETCD server"
sdata=$(etcdctl --peers http://${ETCDSERVER}:${ETCDPORT} get /samanamonitor/data/$id 2>&1)
out=$?
if [ "$out" != "0" ]; then
    echo "Unable to collect data from ETCD server."
    echo $sdata
    finish_test
    exit $out
fi
echo "Data collected."
echo "Checking data"
classes=$(echo $q | jq -r '.queries[] .name')
for c in $classes; do
    o=$(echo $sdata | jq -r ".$c")
    if [ "$o" == "null" ]; then
        echo "* Unable to get class $c from data"
    fi
done
echo "Data checked."
finish_test