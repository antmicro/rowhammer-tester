#include "cmdline.h"

struct args cmdline_args = {
    .pl_mem_base     = 0x400000000,
    .pl_mem_size     = 0x100000000,
    .udp_port        = 1234,
    .server_buf_size = 4096,
    .etherbone_abort = false,
};

#define PARSE_ARG(store, name) do {               \
        if (strcmp(argv[i], name) == 0) {         \
            i++;                                  \
            if (i >= argc) {                      \
                perror("Missing value for" name); \
                exit(1);                          \
            }                                     \
            store = strtoul(argv[i], &res, 0);    \
            if (*res != 0) {                      \
                perror("Wrong value for" name);   \
                exit(1);                          \
            }                                     \
            found = 1;                            \
            continue;                             \
        }                                         \
    } while (0);

#define PARSE_BOOLEAN_ARG(store, name) do {       \
        if (strcmp(argv[i], name) == 0) {         \
            store = true;                         \
            found = 1;                            \
            continue;                             \
        }                                         \
    } while (0);

void parse_args(int argc, char *argv[]) {
    // help message
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            const char *usage =
                "Usage: %s [args...]\n"
                "\n"
                "Options:\n"
                "  --pl-mem-base      Base physical address of memory connected to PL (default: 0x%012lx)\n"
                "  --pl-mem-size      Size of the PL memory area (default: 0x%012lx)\n"
                "  --udp-port         UDP port to use (default: %d)\n"
                "  --server-buf-size  Size of internal server buffer (default: %lu)\n"
                "  --etherbone-abort  Abort on EtherBone packet errors (default: false)\n"
                ;
            printf(usage, argv[0],
                    cmdline_args.pl_mem_base,
                    cmdline_args.pl_mem_size,
                    cmdline_args.udp_port,
                    cmdline_args.server_buf_size);
            exit(0);
        }
    }

    // parse args
    int i = 1;
    while (i < argc) {
        char *res;
        int found = 0;
        PARSE_ARG(cmdline_args.pl_mem_base,     "--pl-mem-base");
        PARSE_ARG(cmdline_args.pl_mem_size,     "--pl-mem-size");
        PARSE_ARG(cmdline_args.udp_port,        "--udp-port");
        PARSE_ARG(cmdline_args.server_buf_size, "--server-buf-size");
        PARSE_BOOLEAN_ARG(cmdline_args.etherbone_abort, "--etherbone-abort");
        if (found == 0) {
            printf("Error: wrong argument: %s\n", argv[i]);
            exit(1);
        }
        ++i;
    }
}
