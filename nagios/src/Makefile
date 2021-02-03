NAGIOS_LIBEXEC ?= $(INSTALL_BASE)/usr/local/nagios/libexec
NAGIOS_USER ?= nagios
NAGIOS_GROUP ?= nagios
FILE_MODE := 0664

INSTALL_FILES = $(wildcard check*)

.PHONY: $(INSTALL_FILES)

install:
	$(MAKE) $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(NAGIOS_GROUP) -o $(NAGIOS_USER) -m $(FILE_MODE) $@ $(NAGIOS_LIBEXEC)/$@