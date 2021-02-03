INSTALL_PATH ?= /etc/nagios/objects/samana
USER ?= nagios
GROUP ?= nagios
MODE ?= 0664

INSTALL_FILES = $(wildcard *.cfg)

install: $(INSTALL_FILES)
	install -D -g $(GROUP) -o $(USER) -m $(MODE) $^ $(INSTALL_PATH)/$^