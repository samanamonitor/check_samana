CFLAGS=-DNDEBUG -g -O3 -Wall -fPIC -Wstrict-prototypes -DMAJOR_VERSION=1 -DMINOR_VERSION=0 -I/usr/include/python3.6m

etcd.so: etcd.o client.o exception.o result.o
	$(CC) -shared $^ -o $@ -lcurl -lpython3.6m -ljansson

test:
	python3 test.py

clean:
	rm -f *.o *.so