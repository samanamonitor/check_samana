NAGIOS_IP=unset

samanamon.ps1: samanamon.ps1.templ
	cat samanamon.psi.templ | sed -e "s/%NAGIOS_IP%/$NAGIOS_IP" > samanamon.ps1

install: samanamon.ps1
	install samanamon.ps1 /var/www/html