HOSTS_DIR := /usr/local/pnp4nagios/var/perfdata
PAGES_DIR := /usr/local/pnp4nagios/etc/pages
HOSTS := $(shell ls -1  $(HOSTS_DIR)/)
PAGES_CONFIG := $(patsubst $(HOSTS_DIR)/%,$(PAGES_DIR)/%,$(HOSTS))
PNP_USER := nagios
PNP_GROUP := nagcmd

all: 
	echo $(HOSTS)
#	for h in $(ls /usr/local/pnp4nagios/var/perfdata); do
#		sed -e "s/%HOST%/$h/" samana-host-summary.cfg-sample > /usr/local/pnp4nagios/var/perfdata/$h.cfg

$(PAGES_DIR)/%.cfg: %.cfg
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@

%.cfg: samana-host-summary.cfg-sample
	sed -e "s/%HOST%/$(patsubst %.cfg,%,$@)/" $< > $@
