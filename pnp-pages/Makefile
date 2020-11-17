HOSTS_DIR := /usr/local/pnp4nagios/var/perfdata
PAGES_DIR := /usr/local/pnp4nagios/etc/pages
HOSTS := $(wildcard $(HOSTS_DIR)/%)
PAGES_CONFIG := $(patsubst $(HOSTS_DIR)/%,$(PAGES_DIR)/%,$(HOSTS))

all: $(PAGES_CONFIG)
#	for h in $(ls /usr/local/pnp4nagios/var/perfdata); do
#		sed -e "s/%HOST%/$h/" samana-host-summary.cfg-sample > /usr/local/pnp4nagios/var/perfdata/$h.cfg

%.cfg: samana-host-summary.cfg-sample
	sed -e "s/%HOST%/$(patsubst %.cfg,%,$@)/" $< > $@
