all:
	for h in $(ls /usr/local/pnp4nagios/var/perfdata); do
		sed -e "s/%HOST%/$h/" samana-host-summary.cfg-sample > /usr/local/pnp4nagios/var/perfdata/$h.cfg