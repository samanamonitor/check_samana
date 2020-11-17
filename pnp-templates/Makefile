TEMPLATE_DIR := /usr/local/pnp4nagios/share/templates
PNP_USER := nagios
PNP_GROUP := nagcmd
SRC_FILES := $(wildcard *.php)
DST_FILES := $(patsubst %.php,$(TEMPLATE_DIR)/%.php,$(SRC_FILES))

install: $(DST_FILES)

$(TEMPLATE_DIR)/%.php: %.php
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@
