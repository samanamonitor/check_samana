LIBS = $(notdir $(wildcard ../lib/*.py))
CUR_DIR = $(realpath .)
IMAGE_NAME = pywmi:v1

all: $(LIBS)
	docker build -t $(IMAGE_NAME) .

$(LIBS):
	cp ../lib/$@ .

pywmi.so:
	wget -qO ./$@.gz https://s3.us-west-2.amazonaws.com/monitor.samanagroup.co/$@.gz
	gunzip $@.gz

$(DIRS):
	$(MAKE) -C $@

clean: $(LIBS)
	rm -f $^
	docker image rm $(IMAGE_NAME)

test:
	docker run -it --rm --name test --mount type=bind,source=$(CUR_DIR),destination=/opt/samana $(IMAGE_NAME) /bin/bash
