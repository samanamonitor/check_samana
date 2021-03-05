#!/bin/bash

FILE_PATH=$1
FILE_NAME=${FILE_PATH##*/}
FILE_DIR=${FILE_PATH%/*}
BAK_FILE=${FILE_NAME%.*}.bak
DS_NUM=$2

if [ -z "$FILE_PATH" ] || [ -z "$DS_NUM" ]; then
    echo "usage: $0 <RRD File path and name> <# of datasets in new rrd>"
    exit 1
fi

mv $FILE_PATH $FILE_DIR/$BAK_FILE

RRA="RRA:AVERAGE:0.5:1:2880 \
    RRA:AVERAGE:0.5:5:2880 \
    RRA:AVERAGE:0.5:30:4320 \
    RRA:AVERAGE:0.5:360:5840 \
    RRA:MAX:0.5:1:2880 \
    RRA:MAX:0.5:5:2880 \
    RRA:MAX:0.5:30:4320 \
    RRA:MAX:0.5:360:5840 \
    RRA:MIN:0.5:1:2880 \
    RRA:MIN:0.5:5:2880 \
    RRA:MIN:0.5:30:4320 \
    RRA:MIN:0.5:360:5840"
DS=""
for i in $(seq 1 $DS_NUM); do
    DS="$DS DS:$i:GAUGE:8460:U:U"
done

rrdtool create $FILE_PATH --step 60 -r $BAK_FILE $DS $RRA
    
