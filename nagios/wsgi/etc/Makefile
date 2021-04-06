APACHE_ETC ?= $(INSTALL_BASE)/etc/apache2/conf-available
WSGI_USER ?= nagios
WSGI_GROUP ?= nagios
WSGI_PROCESSES := 10
WSGI_WWW ?= /usr/local/nagios/share/wsgi
FILE_MODE := 0644
INSTALL_FILES = $(subst .orig,,$(wildcard *.orig))

all: $(INSTALL_FILES)

%.conf: %.conf.orig
	sed -e "s|&WSGI_PROCESSES&|$(WSGI_PROCESSES)|" \
		-e "s|&WSGI_WWW&|$(WSGI_WWW)|" \
		-e "s|&WSGI_USER&|$(WSGI_USER)|" \
		-e "s|&WSGI_GROUP&|$(WSGI_GROUP)|" \
		$< > $@

install: $(INSTALL_FILES)

$(INSTALL_FILES):
	install -D -g $(WSGI_GROUP) -o $(WSGI_USER) -m $(FILE_MODE) $@ $(APACHE_ETC)/$@

clean:
	rm -f *.conf