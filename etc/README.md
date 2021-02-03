# INSTALLATION INSTRUCTIONS FOR THE CONFIGURATION FILES

## Default install
`make install`

## Relevant variables
* INSTALL_BASE default */etc/nagios*
* USER default *nagios*
* GROUP default *nagios*

## Install with variables
`make install INSTALL_BASE=/usr/local/nagios/etc USER=nag GROUP=nagcmd`