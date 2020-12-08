#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>

#include "pl_mmap.h"

int pl_mmap_open(struct pl_mmap *pl_mem, off_t base_address, size_t size) {
    memset(pl_mem, 0, sizeof(struct pl_mmap));

    int mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (mem_fd < 0) {
        perror("Could not open /dev/mem");
        goto error;
    }

    // Truncate offset to a multiple of the page size, or mmap will fail.
    size_t pagesize = sysconf(_SC_PAGE_SIZE);
    off_t page_base = (base_address / pagesize) * pagesize;
    off_t page_offset = base_address - page_base;
    off_t len = page_offset + size;

    void *mem = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, page_base);
    if (mem == MAP_FAILED) {
        perror("Could not map memory");
        pl_mem->mem = MAP_FAILED;
        goto error;
    }

    close(mem_fd);
    pl_mem->mem = mem;
    pl_mem->base = page_base;
    pl_mem->len = len;
    return 0;
error:
    if (mem_fd > 0) {
        close(mem_fd);
    }
    return -1;
}

void pl_mmap_close(struct pl_mmap *pl_mem) {
    if (pl_mem->mem != MAP_FAILED) {
        if (munmap(pl_mem->mem, pl_mem->len) == -1) {
            perror("Could not unmap memory");
        }
    }
}
