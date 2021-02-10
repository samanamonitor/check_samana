INSTALL_BASE ?= /etc/nagios/

DIRS = $(wildcard */.)

.PHONY: $(DIRS)

install: $(DIRS)

$(DIRS):
	$(MAKE) -C $@