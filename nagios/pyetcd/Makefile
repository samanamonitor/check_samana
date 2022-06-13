PYTHON_VER=3.6
CFLAGS=-DNDEBUG -g -O3 -Wall -fPIC -Wstrict-prototypes \
	-DMAJOR_VERSION=1 -DMINOR_VERSION=0 \
	-I/usr/include/python$(PYTHON_VER)m

etcd.so: etcd.o client.o exception.o result.o
	$(CC) -shared $^ -o $@ -lcurl -lpython$(PYTHON_VER)m -ljansson

install:


test:
	python3 test.py

clean:
	rm -f *.o *.so