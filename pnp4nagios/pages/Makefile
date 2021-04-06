HOSTS_DIR := /usr/local/pnp4nagios/var/perfdata
PAGES_DIR := /usr/local/pnp4nagios/etc/pages
HOSTS := $(shell ls -1  $(HOSTS_DIR)/)
PAGES_CONFIG := $(patsubst %,$(PAGES_DIR)/%.cfg,$(HOSTS))
PNP_USER := nagios
PNP_GROUP := nagcmd


all:
	: "Not Implemented"

install:
	: "Not Implemented"

$(PAGES_DIR)/%.cfg: %.pre
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@

%.pre: samana-host-summary.cfg-sample
	sed -e "s/%HOST%/$(patsubst %.pre,%,$@)/" $< > $@

clean: