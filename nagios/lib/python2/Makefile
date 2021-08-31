PYTHON_LIB ?= /usr/lib/python2.7/dist-packages/samana
FILE_MODE := 0755

SRC_FILES = $(wildcard *.py)
DST_FILES = $(addprefix $(PYTHON3_LIB)/,$(SRC_FILES))

.PHONY: $(DST_FILES) $(PYTHON3_LIB)/%.py

all:
	
install: $(DST_FILES)

$(DST_FILES): $(SRC_FILES)
	install -D -g root -o root -m $(FILE_MODE) $(notdir $@) $@

clean:
	rm -f $(DST_FILES)
	rm -Rf $(PYTHON3_LIB)
