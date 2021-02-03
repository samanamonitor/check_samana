<?php
#
# Copyright (c) 2006-2010 Joerg Linge (http://www.pnp4nagios.org)
# Plugin: check_load
#
$opt[1] = "--vertical-label 'Citrix Load Index' -l0 --upper-limit 10000 --color CANVAS#F2F2F2 --color BACK#E2F2FC --title \"Citrix Load Index for $hostname / $servicedesc\" ";
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
$def[1] .= rrd::area("var1", "#F66444", "Citrix Load Index") ;
$def[1] .= rrd::gprint("var1", array("LAST", "AVERAGE", "MAX"), "%6.2lf");
?>
