#!/bin/bash
################################################
###### Bandwidth Usage Calculator          #
#####   by Gabriele Cozzi            ##
####    gabry8086@gmail.com            ###
### Requirements                     ####
##  Snmpwalk + bc                  #####
###########################################
usage="
Usage: check_bw.sh -H hostname -b connectionspeed -v snmp version -m input|output -C community -i interface -p pollingtime


####List of Available Parameters
-H Hostname of snmp you want to check
-b Maximum speed of your connection in Mb/s (this script is intended to work with synchronous connections)
-v (1|2c) Snmp version
-m (input|output) Specify the direction of the bandwidth you want to check
-C (some text here) Specify the name of the community associated with your host
-i (Interface Name) Specify the interface name that you want to monitor (eg: eth0)
-w (optional) set the warning parameter in Mb/s that is going to be passed to nagios
-c (optional) set the critical parameter in Mb/s that is going to be passed to nagios
-h Print this help screen
-p Polling Time in second

"
#Define oid's
oidIN=1.3.6.1.2.1.2.2.1.10
oidOUT=1.3.6.1.2.1.2.2.1.16
mbmulti=1048576
#mbmulti is needed to convert mib to bit
#
# Get Options
while getopts H:b:m:c:v:w:C:i:p:help:h option;
do
        case $option in
                H) hostname=$OPTARG;;
        b) speed=$OPTARG;;
                m) mode=$OPTARG;;
                C) community=$OPTARG;;
        v) version=$OPTARG;;
        i) interface=$OPTARG;;
        p) delta=$OPTARG;;
                w) warning=$OPTARG;;
        c) critical=$OPTARG;;
        h) help=1;;
    esac
done

#Check parameters function
check()
{

if [ ! -z "$help" ]
then
echo "$usage"
exit;
fi

if [ -z "$hostname" ] || [ -z "$community" ] || [ -z "$mode" ] || [ -z "$version" ] || [ -z "$speed" ] || [ -z "$interface" ] || [ -z "$delta" ] && [ "$help" != "1" ]
then
        echo "
** Hostname, speed, community, version, interface and mode parameters are mandatory"
        echo "$usage"
        exit;
fi
case $mode in 
input)
    oid=$oidIN;;
output)
    oid=$oidOUT;;

*) 
echo "Only 'input' or 'output' are acceptable value for 'mode' parameter"
echo "$usage"
exit $incorrect
esac
}

#Nagios Results Return function
nagios_r()
{
    if [ -z "$warning" ] || [ -z "$critical" ]
    then
    echo "Current $mode bandwidth usage is $final Mb/s, $perc% used"
    exit 0;
    fi
    fcomp=`echo "$final*1000" | bc`
    wcomp=`echo "$warning*1000" | bc`
    ccomp=`echo "$critical*1000" | bc`
    if [ `echo ${fcomp%.*}` -lt  `echo ${wcomp%.*}` ]
    then
    echo "OK $mode bandwidth usage is $final Mb/s, $perc% used"
    exit 0;
    fi
    if [ `echo ${fcomp%.*}` -ge  `echo ${wcomp%.*}` ] && [ `echo ${fcomp%.*}` -lt `echo ${ccomp%.*}` ]
    then
    echo "Warning: Current $mode bandwidth usage is $final Mb/s, $perc% used"
    exit 1;
    fi
    if [ `echo ${fcomp%.*}` -ge `echo ${ccomp%.*}` ]
    then 
    echo "Critical: Current $mode bandwidth usage is $final Mb/s, $perc% used"
    exit 2;
    fi

    
}


#Calculate Function
get_value()
{
ifindex=`/usr/bin/snmpwalk -v $version -c $community $hostname 1.3.6.1.2.1.31.1.1.1.1 | grep $interface | grep -o "\.[0-9]*\ "`
speed=`echo "$speed*$mbmulti" | bc`
parRes="-t 10 -v $version -c $community $hostname $oid$ifindex"
result1=`/usr/bin/snmpwalk $parRes | sed -e 's/.*: //'`
sleep $delta
result2=`/usr/bin/snmpwalk $parRes | sed -e 's/.*: //'`

exp1=`echo "($result2-$result1)*8"| bc`
perc=`echo "scale=2; ($exp1/($delta*$speed))*100" | bc`
final=`echo "scale=3; ($exp1/$delta)/$mbmulti" | bc`
if [ "`echo "$final" | awk '{print substr ($0,0,1)}'`" =  "." ]
then
final=`echo $final | awk '{printf "%.3f", $0}'`
fi
}

check
get_value

#this because the oid's counter used are integer and they may reset if they reach the max value allowed so $final will result in a negative number, this will restart the calculaton
if [ "`echo "$final" | awk '{print substr ($0,0,1)}'`" =  "-" ]
then
get_value
fi

nagios_r
