INSTALL_BASE ?= /etc/nagios/

DIRS = $(sort $(dir $(wildcard ../objects/*/)))

.PHONY: $(DIRS)

install: $(DIRS)

$(DIRS):
	$(MAKE) -C $@ INSTALL_BASE=$(INSTALL_BASE)/objects