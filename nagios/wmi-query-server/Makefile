LIBS = $(notdir $(wildcard ../lib/*.py))
CUR_DIR = $(realpath .)
IMAGE_NAME = pywmi:v1

all: $(LIBS) pywmi.so
	docker build -t $(IMAGE_NAME) .

$(LIBS):
	cp ../lib/$@ .

pywmi.so:
	wget -qO ./$@.gz https://s3.us-west-2.amazonaws.com/monitor.samanagroup.co/$@.gz
	gunzip $@.gz

$(DIRS):
	$(MAKE) -C $@

rebuild:
	docker image rm $(IMAGE_NAME)
	docker build -t $(IMAGE_NAME) .

clean: $(LIBS) pywmi.so
	rm -f $^
	docker image rm $(IMAGE_NAME)

test:
	$(CUR_DIR)/test.sh
