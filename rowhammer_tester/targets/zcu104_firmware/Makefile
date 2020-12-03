all: pl_mmap

pl_mmap: main.c pl_mmap.c pl_mmap.h
	aarch64-linux-gnu-gcc -Wall main.c pl_mmap.c -o pl_mmmap

clean:
	rm -f pl_mmap
