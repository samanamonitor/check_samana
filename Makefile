INSTALLERS := nagios pnp4nagios

.PHONY: $(INSTALLERS)

install: $(INSTALLERS)

$(INSTALLERS):
	$(MAKE) -C $(INSTALLERS) install