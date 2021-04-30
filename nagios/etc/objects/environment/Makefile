INSTALL_BASE ?= /usr/local
NAGIOS_BASE ?= $(INSTALL_BASE)/nagios
NAGIOS_ETC ?= $(NAGIOS_BASE)/etc
CUSTOMER ?= environment
INSTALL_PATH ?= $(NAGIOS_ETC)/objects/$(CUSTOMER)
NAGIOS_USER ?= nagios
NAGIOS_GROUP ?= nagios
FILE_MODE ?= 0664

INSTALL_FILES = $(wildcard *.cfg)

.PHONY: $(INSTALL_FILES)

all:
	
install: $(INSTALL_FILES)
	$(eval ACTIVE_CONFIG := $(shell grep -e "^cfg_dir=$(INSTALL_PATH)" $(NAGIOS_ETC)/nagios.cfg))
ifeq ("$(ACTIVE_CONFIG)", "")
	echo "cfg_dir=$(INSTALL_PATH)" >> $(NAGIOS_ETC)/nagios.cfg
endif

$(INSTALL_FILES):
	install -D -g $(NAGIOS_GROUP) -o $(NAGIOS_USER) -m $(FILE_MODE) $@ $(INSTALL_PATH)/$@

clean: