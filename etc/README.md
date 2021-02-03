# INSTALLATION INSTRUCTIONS FOR THE CONFIGURATION FILES

## Default install
`make install`

## Relevant variables
* INSTALL_BASE default */* which will put all files in */etc/nagios/objects*
* USER default *nagios*
* GROUP default *nagios*
* CUSTOMER default *environment*

## Install with variables
`make install INSTALL_BASE=/usr/local/nagios/etc USER=nag GROUP=nagcmd`