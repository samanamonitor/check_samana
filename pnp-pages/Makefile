HOSTS_DIR := /usr/local/pnp4nagios/var/perfdata
PAGES_DIR := /usr/local/pnp4nagios/etc/pages
HOSTS := $(shell ls -1  $(HOSTS_DIR)/)
PAGES_CONFIG := $(patsubst %,$(PAGES_DIR)/%.cfg,$(HOSTS))
PNP_USER := nagios
PNP_GROUP := nagcmd

all: $(PAGES_CONFIG)

$(PAGES_DIR)/%.cfg: %.cfg
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@

%.cfg: samana-host-summary.cfg-sample
	sed -e "s/%HOST%/$(patsubst %.cfg,%,$@)/" $< > $@
