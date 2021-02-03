# INSTALLATION INSTRUCTIONS FOR THE CONFIGURATION FILES

## Default install
`make install`

## Relevant variables
* INSTALL_BASE default */*
* NAGIOS_LIBEXEC default *$(INSTALL_BASE)/usr/local/nagios/libexec*
* NAGIOS_USER default *nagios*
* NAGIOS_GROUP default *nagios*

## Install with variables
`make install NAGIOS_LIBEXEC=/usr/local/nagios/etc USER=nag GROUP=nagcmd`