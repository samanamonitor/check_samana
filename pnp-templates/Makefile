TEMPLATE_DIR := /usr/local/pnp4nagios/share/templates
PNP_USER := nagios
PNP_GROUP := nagcmd
SRC_FILES := $(wildcard *.php)

all: $(TEMPLATE_DIR)
	

$(TEMPLATE_DIR)/%.php: %.php
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@
