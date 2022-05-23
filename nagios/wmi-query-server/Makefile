LIBS = $(notdir $(wildcard ../lib/*.py))
CUR_DIR = $(realpath .)
IMAGE_VERSION = v1
IMAGE_NAME = pywmi:$(IMAGE_VERSION)
IMAGE_TAR = pywmi_$(IMAGE_VERSION).tar
IMAGE_FILE = $(IMAGE_TAR).gz
S3BUCKET = monitor.samanagroup.co

all build: $(LIBS) pywmi.so
	docker build -t $(IMAGE_NAME) .

$(LIBS):
	cp ../lib/$@ .

pywmi.so:
	wget -qO ./$@.gz https://s3.us-west-2.amazonaws.com/$(S3BUCKET)/$@.gz
	gunzip $@.gz

rebuild:
	docker image rm $(IMAGE_NAME)
	$(MAKE) build

clean:
	rm -f $(LIBS) pywmi.so $(IMAGE_TAR) $(IMAGE_FILE)
	docker image rm $(IMAGE_NAME)

test:
	$(CUR_DIR)/test.sh

$(IMAGE_TAR):
	docker image save $(IMAGE_NAME) > $@

dist $(IMAGE_FILE): $(IMAGE_TAR)
	gzip -f $^

upload: $(IMAGE_FILE)
	aws s3api put-object --bucket $(S3BUCKET) --key $^ --body $^ --acl public-read

download:
	wget -qO $(IMAGE_FILE) https://s3.us-west-2.amazonaws.com/$(S3BUCKET)/$(IMAGE_FILE)
