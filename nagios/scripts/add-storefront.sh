#!/bin/bash

SFID=$1
CONTNAME=$2

if [ -z "$SFID" ]; then
    echo "Usage: $0 <storefront ID>"
    exit 1
fi

if [ -z "${CONTNAME}" ]; then
    sample=$(etcdctl get /samanamonitor/config/storefront-example)
    etcdctl set /samanamonitor/config/$SFID \
        "$sample"
else
    sample=$(docker exec -it ${CONTNAME} etcdctl get /samanamonitor/config/storefront-example)
    docker exec -it ${CONTNAME} etcdctl set /samanamonitor/config/$SFID "$sample"
fi