#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#include "pl_mmap.h"

int main(int argc, char *argv[])
{
    if (argc < 2) {
        printf("Usage: %s <addr>\n", argv[0]);
        printf("Reads addr.\n");
        return 0;
    }

    off_t offset = strtoul(argv[1], NULL, 0);

    struct pl_mmap pl_mem;
    if (pl_mmap_open(&pl_mem, PL_MEM_BASE, PL_MEM_SIZE) < 0) {
        return 1;
    }

    uint32_t *addr = pl_mem.mem + offset;
    uint32_t data = *addr;
    printf("0x%08lx: 0x%08x\n", offset, data);

    pl_mmap_close(&pl_mem);

    return 0;

    return 0;
}
