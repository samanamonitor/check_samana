INSTALL_BASE ?= /

DIRS = $(wildcard */.)

.PHONY: $(DIRS)

install: $(DIRS)

$(DIRS):
	$(MAKE) -C $@