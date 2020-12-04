#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "pl_mmap.h"
#include "udp_server.h"

enum command {
    CMD_WRITE,
    CMD_READ,
    CMD_SERVER,
};

int server_callback(char *buf, size_t buf_size, size_t recv_len) {
    printf("Received %lu bytes\n", recv_len);
    strcpy(buf, "Roger that");
    return strlen(buf);
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        printf("Usage: %s (server | read <addr> | write <addr> <value>)\n", argv[0]);
        printf("Reads addr.\n");
        return 0;
    }

    const char* cmd_s = argv[1];
    enum command cmd;
    if (strcmp(cmd_s, "read") == 0) {
        cmd = CMD_READ;
    } else if (strcmp(cmd_s, "write") == 0) {
        cmd = CMD_WRITE;
    } else if (strcmp(cmd_s, "server") == 0) {
        cmd = CMD_SERVER;
    } else {
        printf("Wrong command: %s\n", cmd_s);
        return 1;
    }

    off_t offset = 0;
    uint32_t value = 0;
    if (cmd == CMD_READ || cmd == CMD_WRITE) {
        if (argc < 3) {
            printf("Missing address\n");
            return 1;
        }
        offset = strtoul(argv[2], NULL, 0);
    }
    if (cmd == CMD_WRITE) {
        if (argc < 4) {
            printf("Missing write value\n");
            return 1;
        }
        value = strtoul(argv[3], NULL, 0);
    }

    struct pl_mmap pl_mem;
    if (pl_mmap_open(&pl_mem, PL_MEM_BASE, PL_MEM_SIZE) < 0) {
        return 2;
    }

    uint32_t *addr = pl_mem.mem + offset;

    int ret = 0;
    switch (cmd) {
        case CMD_READ:
            printf("0x%08lx: 0x%08x\n", offset, *addr);
            break;
        case CMD_WRITE:
            printf("0x%08lx = 0x%08x\n", offset, value);
            *addr = value;
            break;
        case CMD_SERVER:
            if (udp_server_run(1234, 4096, &server_callback) != 0) {
                ret = 3;
            }
            break;
        default:
            ret = 4;
    }

    pl_mmap_close(&pl_mem);

    return ret;
}

