LIBS = $(notdir $(wildcard ../lib/*.py))

all: $(LIBS)
	docker build -t pywmi:v1 .

$(LIBS):
	cp ../lib/$@ .

$(DIRS):
	$(MAKE) -C $@

clean: $(LIBS)
	rm -f $^


test:
	docker run -it --rm --name test --mount type=bind,source=$(pwd),destination=/opt/samana pywmi:v1 /bin/bash
