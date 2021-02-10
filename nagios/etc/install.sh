#!/bin/bash

NAGIOS_ETC=/etc/nagios
NAGIOS_CFG=${NAGIOS_ETC}/nagios.cfg
CUSTOMER=environment

enable() {
    CFG_DIR="cfg_dir=${NAGIOS_ETC}/objects/samana"
    if $(grep -q "${CFG_DIR}" ${NAGIOS_CFG}); then 
        echo "${CFG_DIR}" >> ${NAGIOS_CFG};
    fi

    CFG_DIR="cfg_dir=${NAGIOS_ETC}/objects/${CUSTOMER}"
    if $(grep -q "${CFG_DIR}" ${NAGIOS_CFG}); then 
        echo "${CFG_DIR}" >> ${NAGIOS_CFG};
    fi    
}

disable() {
    sed -i -e "/#cfg_dir=${NAGIOS_ETC}/objects/${CUSTOMER}/d"
    sed -i -e "/#cfg_dir=${NAGIOS_ETC}/objects/samana/d"
}

if [ ! -f ${NAGIOS_CFG} ]; then
    echo "Cannot enable. File ${NAGIOS_CFG} doesn't exist."
    exit 1
fi

case "$1" in
'enable')
    enable
    ;;
'disable')
    disable
    ;;
*)
    ;;
esac