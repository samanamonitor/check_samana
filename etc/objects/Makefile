INSTALL_BASE ?= /etc/nagios/

DIRS = $(sort $(dir $(wildcard ../objects/*/)))

install:
	$(MAKE) -C $(DIRS) INSTALL_BASE=$(INSTALL_BASE)/objects
