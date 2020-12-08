#ifndef DEBUG_H
#define DEBUG_H

#ifndef NDEBUG
// debug
#define dbg_printf(...) printf(__VA_ARGS__)
#define dbg_memdump(mem, len) _memdump(mem, len)
#define dbg_memdumpf(mem, len, file) _memdumpf(mem, len, file)

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define CEIL(a, b)  ((a)/(b) + (((a) % (b)) != 0))
static inline void _memdump(void *mem, size_t len) {
    uint8_t *bytes = mem;
    for (size_t i = 0; i < CEIL(len, 8); ++i) {
        for (size_t j = 0; j < 8; ++j) {
            if (8*i + j >= len) break;
            printf("%02x ", bytes[8*i + j]);
        }
        printf("\n");
    }
}
#undef CEIL

static inline void _memdumpf(void *mem, size_t len, const char *dumpfile) {
    FILE *f = fopen(dumpfile, "w");
    fwrite(mem, len, 1, f);
    fclose(f);
}

#else
// release
#define dbg_printf(...) ((void) 0)
#define dbg_memdump(mem, len) ((void) 0)
#define dbg_memdumpf(mem, len, file) ((void) 0)
#endif


#endif /* DEBUG_H */
