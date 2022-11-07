
PYTHON3_LIB ?= /usr/local/nagios/libexec/lib/python3/dist-packages/sammwr
SRC_FILES = $(wildcard *.py)
DST_FILES = $(addprefix $(PYTHON3_LIB)/,$(SRC_FILES))
FILE_MODE := 0755

.PHONY: $(DST_FILES) $(PYTHON3_LIB)/%.py

install: $(DST_FILES)

$(DST_FILES): $(SRC_FILES)
	install -D -g root -o root -m $(FILE_MODE) $(notdir $@) $@
