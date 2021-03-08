#!/bin/bash

SFID=$1

if [ -z "$SFID" ]; then
    echo "Usage: $0 <storefront ID>"
    exit 1
fi

etcdctl set /samanamonitor/config/$SFID "$(etcdctl get /samanamonitor/config/storefront-example)"