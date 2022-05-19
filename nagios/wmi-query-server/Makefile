LIBS = $(notdir $(wildcard ../lib/*.py))
CUR_DIR = $(realpath .)
IMAGE_NAME = pywmi:v1

all build: $(LIBS) pywmi.so
	docker build -t $(IMAGE_NAME) .

$(LIBS):
	cp ../lib/$@ .

pywmi.so:
	wget -qO ./$@.gz https://s3.us-west-2.amazonaws.com/monitor.samanagroup.co/$@.gz
	gunzip $@.gz

rebuild:
	docker image rm $(IMAGE_NAME)
	$(MAKE) build

clean:
	rm -f $(LIBS) pywmi.so pywmi_v1.tar pywmi_v1.tar.gz
	docker image rm $(IMAGE_NAME)

test:
	$(CUR_DIR)/test.sh

pywmi_v1.tar:
	docker image save $(IMAGE_NAME) > $@

dist pywmi_v1.tar.gz: pywmi_v1.tar
	gzip pywmi_v1.tar

upload: pywmi_v1.tar.gz
	aws s3api put-object --bucket monitor.samanagroup.co --key $^ --body $^ --acl public-read
