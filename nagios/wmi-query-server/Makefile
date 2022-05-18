LIBS = $(notdir $(wildcard ../lib/*.py))
CUR_DIR = $(realpath .)

all: $(LIBS)
	docker build -t pywmi:v1 .

$(LIBS):
	cp ../lib/$@ .

$(DIRS):
	$(MAKE) -C $@

clean: $(LIBS)
	rm -f $^


test:
	docker run -it --rm --name test --mount type=bind,source=$(CUR_DIR),destination=/opt/samana pywmi:v1 /bin/bash
