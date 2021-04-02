#ifndef ETHERBONE_H
#define ETHERBONE_H

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "debug.h"

#define ETHERBONE_HEADER_LENGTH 8
#define ETHERBONE_RECORD_HEADER_LENGTH 4

struct etherbone_record {
    union {
        uint32_t write_value;
        uint32_t read_addr;
    };
} __attribute__((packed));

struct etherbone_record_header {
    uint8_t bca: 1;
    uint8_t rca: 1;
    uint8_t rff: 1;
    uint8_t _reserved: 1;
    uint8_t cyc: 1;
    uint8_t wca: 1;
    uint8_t wff: 1;
    uint8_t _reserved2: 1;
    uint8_t byte_enable;
    uint8_t wcount;
    uint8_t rcount;
    // uint32_t padding;
    union {
        uint32_t base_write_addr;
        uint32_t base_ret_addr;
    };
} __attribute__((packed));

struct etherbone_packet {
    uint16_t magic;
    uint8_t pf: 1;
    uint8_t pr: 1;
    uint8_t nr: 1;
    uint8_t _reserved: 1;
    uint8_t version: 4;
    uint8_t port_size: 4;
    uint8_t addr_size: 4;
    uint32_t _padding;

    struct etherbone_record_header record_hdr;
    struct etherbone_record record[];
} __attribute__((packed, aligned(8)));

// Memory write/read callbacks
typedef void (*etherbone_write)(void *arg, uint32_t addr, uint32_t value);
typedef uint32_t (*etherbone_read)(void *arg, uint32_t addr);

struct etherbone_memory_handlers {
    void *arg;
    etherbone_write write;
    etherbone_read read;
};

int etherbone_callback(struct etherbone_memory_handlers *mem,
        uint8_t *buf, size_t buf_size, size_t recv_len);

#endif /* ETHERBONE_H */
