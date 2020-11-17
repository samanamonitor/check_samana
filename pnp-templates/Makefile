TEMPLATE_DIR := /usr/local/pnp4nagios/share/templates
PNP_USER := nagios
PNP_GROUP := nagcmd

$(TEMPLATE_DIR)/%.php: %.php
	install -o $(PNP_USER) -g $(PNP_GROUP) $^ $@
