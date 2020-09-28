all:
	$(MAKE) etc
	$(MAKE) winsrc
	$(MAKE) src

src:
	$(MAKE) -C src install

etc:
	$(MAKE) -C etc install

winsrc:
	$(MAKE) -C winsrc install