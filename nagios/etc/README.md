# INSTALLATION INSTRUCTIONS FOR THE CONFIGURATION FILES

## Default install
`make install`

## Relevant variables
* INSTALL_BASE default */*
* NAGIOS_ETC default *$(INSTALL_BASE)/etc/nagios*
* NAGIOS_USER default *nagios*
* NAGIOS_GROUP default *nagios*
* CUSTOMER default *environment*

## Install with variables
`make install INSTALL_BASE=/usr/local/nagios/etc USER=nag GROUP=nagcmd`