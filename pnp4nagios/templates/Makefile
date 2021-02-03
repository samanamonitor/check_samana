PNP_BASE ?= $(INSTALL_BASE)/usr/local/pnp4nagios/
PNP_SHARE ?= $(PNP_BASE)/share
TEMPLATE_DIR := $(PNP_SHARE)/templates
PNP_USER ?= nagios
PNP_GROUP ?= nagios
FILE_MODE := 0664

INSTALL_FILES := $(wildcard *.php)

.PHONY: $(INSTALL_FILES)

install:
	$(MAKE) $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(PNP_GROUP) -o $(PNP_USER) -m $(FILE_MODE) $@ $(TEMPLATE_DIR)/$@
