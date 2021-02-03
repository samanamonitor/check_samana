INSTALL_BASE ?= /etc/nagios/objects
INSTALL_PATH ?= $(INSTALL_BASE)/samana
USER ?= nagios
GROUP ?= nagios
MODE ?= 0664

INSTALL_FILES = $(wildcard *.cfg)

install:
	$(MAKE) $(INSTALL_FILES)

.PHONY: $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(GROUP) -o $(USER) -m $(MODE) $@ $(INSTALL_PATH)/$@
