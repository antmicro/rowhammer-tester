#ifndef PL_MMAP_H
#define PL_MMAP_H

#include <sys/mman.h>

struct pl_mmap {
    void *mem;
    off_t base;
    size_t len;
};

int pl_mmap_open(struct pl_mmap *pl_mem, off_t base_address, size_t size);
void pl_mmap_close(struct pl_mmap *pl_mem);

#endif /* PL_MMAP_H */
