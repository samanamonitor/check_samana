INSTALL_BASE ?= /usr/local/pnp4nagios/
PNP_USER ?= nagios
PNP_GROUP ?= nagcmd
TEMPLATE_DIR := $(INSTALL_BASE)/share/templates
SRC_FILES := $(wildcard *.php)
DST_FILES := $(patsubst %.php,$(TEMPLATE_DIR)/%.php,$(SRC_FILES))

install: $(DST_FILES)

$(TEMPLATE_DIR)/%.php: %.php
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@
