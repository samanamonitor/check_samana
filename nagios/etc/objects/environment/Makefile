NAGIOS_ETC ?= $(INSTALL_BASE)/etc/nagios
INSTALL_PATH ?= $(NAGIOS_ETC)/objects/$(CUSTOMER)
CUSTOMER ?= environment
NAGIOS_USER ?= nagios
NAGIOS_GROUP ?= nagios
FILE_MODE ?= 0664

INSTALL_FILES = $(wildcard *.cfg)

.PHONY: $(INSTALL_FILES)

all:
	
install: $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(NAGIOS_GROUP) -o $(NAGIOS_USER) -m $(FILE_MODE) $@ $(INSTALL_PATH)/$@

clean: