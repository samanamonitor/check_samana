WSGI_USER ?= nagios
WSGI_GROUP ?= nagios
WSGI_PROCESSES := 10
WSGI_WWW ?= /usr/local/nagios/share/wsgi
FILE_MODE := 0755


INSTALL_FILES = $(wildcard *.py)

.PHONY: $(INSTALL_FILES)

all:

install: $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(WSGI_GROUP) -o $(WSGI_USER) -m $(FILE_MODE) $@ $(WSGI_WWW)/

clean:
