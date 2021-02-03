<?php
#
# Copyright (c) 2006-2010 Joerg Linge (http://www.pnp4nagios.org)
# Plugin: check_load
#
$opt[1] = "--vertical-label CPU -l0 --upper-limit 100 --color CANVAS#C9E2F2 --color BACK#E2F2FC --title \"CPU Load for $hostname / $servicedesc\" ";
#
#
#
$def[1]  = rrd::def("var1", $RRDFILE[1], $DS[1], "AVERAGE");

if ($WARN[1] != "") {
    $def[1] .= "HRULE:$WARN[1]#FFE459 ";
}
if ($CRIT[1] != "") {
    $def[1] .= "HRULE:$CRIT[1]#FF0000 ";       
}
$def[1] .= rrd::area("var1", "#1A8DD8", "CPU %") ;
$def[1] .= rrd::gprint("var1", array("LAST", "AVERAGE", "MAX"), "%6.2lf");
?>
