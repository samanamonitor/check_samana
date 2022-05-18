LIBS = $(notdir $(wildcard ../lib/*.py))

all: $(LIBS)
	docker build -t pywmi:v1 .

$(LIBS):
	cp ../lib/$@ .

$(DIRS):
	$(MAKE) -C $@

clean: $(LIBS)
	rm -f $^


install: $(patsubst %,install_%,$(DIRS))


install_%:
	$(MAKE) -C $(subst install_,,$@) install
	mkdir -p $(WSGI_WWW)
	ln -sf $(NAGIOS_LIBEXEC)/check_winrm.py $(WSGI_WWW)

clean_%:
	$(MAKE) -C $(subst clean_,,$@) clean