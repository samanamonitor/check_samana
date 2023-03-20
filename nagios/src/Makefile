NAGIOS_LIBEXEC ?= $(INSTALL_BASE)/usr/local/nagios/libexec
NAGIOS_USER ?= nagios
NAGIOS_GROUP ?= nagios
FILE_MODE := 0755

INSTALL_FILES = $(wildcard check*) slack_nagios.pl samanaetcd.py sammworker.py

.PHONY: $(INSTALL_FILES)

all:
	
install: $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(NAGIOS_GROUP) -o $(NAGIOS_USER) -m $(FILE_MODE) $@ $(DESTDIR)$(NAGIOS_LIBEXEC)/$@

clean: