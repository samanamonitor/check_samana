INSTALL_BASE ?= /usr/local
NAGIOS_BASE ?= $(INSTALL_BASE)/nagios
NAGIOS_ETC ?= $(NAGIOS_BASE)/etc
DIRS = $(subst /.,,$(wildcard */.))


.PHONY: $(DIRS)

all: $(DIRS)

$(DIRS):
	$(MAKE) -C $@

clean: $(patsubst %,clean_%,$(DIRS))


install: $(patsubst %,install_%,$(DIRS))
	./install.sh enable


install_%:
	$(MAKE) -C $(subst install_,,$@) install

clean_%:
	$(MAKE) -C $(subst clean_,,$@) clean


