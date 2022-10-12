APACHE_ETC_UBUNTU ?= $(INSTALL_BASE)/etc/apache2/conf-available
APACHE_ETC_CENTOS ?= $(INSTALL_BASE)/etc/httpd/conf.d
WSGI_USER ?= nagios
WSGI_GROUP ?= nagios
WSGI_PROCESSES := 10
WSGI_WWW ?= /usr/local/nagios/share/wsgi
FILE_MODE := 0644
INSTALL_FILES = $(subst .orig,,$(wildcard *.orig))

dummy:
	$(info "skipping installation of check_winrm wsgi")

all: $(INSTALL_FILES)

%.conf: %.conf.orig
	sed -e "s|&WSGI_PROCESSES&|$(WSGI_PROCESSES)|" \
		-e "s|&WSGI_WWW&|$(WSGI_WWW)|" \
		-e "s|&WSGI_USER&|$(WSGI_USER)|" \
		-e "s|&WSGI_GROUP&|$(WSGI_GROUP)|" \
		$< > $@

install:
	$(info skipping installation of check_winrm wsgi)

install-: $(patsubst %,install_%,$(INSTALL_FILES))

install_$(INSTALL_FILES):
ifneq ("$(wildcard $(APACHE_ETC_UBUNTU))","")
	install -D -g $(WSGI_GROUP) -o $(WSGI_USER) -m $(FILE_MODE) $(subst install_,,$@) $(APACHE_ETC_UBUNTU)/$(subst install_,,$@)
	a2enconf check_winrm
else
	install -D -g $(WSGI_GROUP) -o $(WSGI_USER) -m $(FILE_MODE) $(subst install_,,$@) $(APACHE_ETC_CENTOS)/$(subst install_,,$@)
endif


clean:
	rm -f *.conf