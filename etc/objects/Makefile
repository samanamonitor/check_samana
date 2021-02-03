INSTALL_BASE ?= /etc/nagios/

DIRS = $(sort $(dir $(wildcard ../objects/*/)))

.PHONY: $(DIRS)

install:
	$(MAKE) -C $(DIRS) INSTALL_BASE=$(INSTALL_BASE)/objects
