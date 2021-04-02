#ifndef CMDLINE_H
#define CMDLINE_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

struct args {
    off_t pl_mem_base;
    size_t pl_mem_size;
    int udp_port;
    size_t server_buf_size;
    bool etherbone_abort;
};

extern struct args cmdline_args;

void parse_args(int argc, char *argv[]);

#endif /* CMDLINE_H */
