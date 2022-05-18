.PHONY: $(DIRS)
LIBS = $(notdir $(wildcard ../lib/*.py))

all: $(LIBS)
	echo $^

$(LIBS):
	cp ../lib/$@ .

$(DIRS):
	$(MAKE) -C $@

clean: $(patsubst %,clean_%,$(DIRS))


install: $(patsubst %,install_%,$(DIRS))


install_%:
	$(MAKE) -C $(subst install_,,$@) install
	mkdir -p $(WSGI_WWW)
	ln -sf $(NAGIOS_LIBEXEC)/check_winrm.py $(WSGI_WWW)

clean_%:
	$(MAKE) -C $(subst clean_,,$@) clean