HTML_PATH ?= $(INSTALL_BASE)/var/www/html
CONTAINER_HTML ?= /usr/local/apache2/html
NAGIOS_USER ?= nagios
NAGIOS_GROUP ?= nagios
FILE_MODE := 0664
INSTALL_FILES = $(wildcard *.ps1)

.PHONY: $(INSTALL_FILES)

all:
	
install: $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(NAGIOS_GROUP) -o $(NAGIOS_USER) -m $(FILE_MODE) $@ $(HTML_PATH)/$@
	install -D -g $(NAGIOS_GROUP) -o $(NAGIOS_USER) -m $(FILE_MODE) $@ $(CONTAINER_HTML)/$@

clean:
