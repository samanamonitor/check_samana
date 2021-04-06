INSTALL_BASE ?= /etc/nagios/

DIRS = $(subst /.,,$(wildcard */.))


.PHONY: $(DIRS)

all: $(DIRS)
	
$(DIRS):
	$(MAKE) -C $@

clean: $(patsubst %,clean_%,$(DIRS))


install: $(patsubst %,install_%,$(DIRS))


install_%:
	$(MAKE) -C $(subst install_,,$@) install

clean_%:
	$(MAKE) -C $(subst clean_,,$@) clean
