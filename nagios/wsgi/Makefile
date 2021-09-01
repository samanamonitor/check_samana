INSTALL_BASE ?= /
NAGIOS_LIBEXEC ?= /usr/local/nagios/libexec
WSGI_WWW ?= /usr/local/nagios/share/wsgi
DIRS = $(subst /.,,$(wildcard */.))

.PHONY: $(DIRS)

$(DIRS):
	$(MAKE) -C $@

clean: $(patsubst %,clean_%,$(DIRS))


install: $(patsubst %,install_%,$(DIRS))


install_%:
	$(MAKE) -C $(subst install_,,$@) install
	mkdir -p $(WSGI_WWW)
	ln -s $(NAGIOS_LIBEXEC)/check_winrm.py $(WSGI_WWW)

clean_%:
	$(MAKE) -C $(subst clean_,,$@) clean