#include "etherbone.h"

#include <arpa/inet.h>

#define DUMP(packet) dbg_memdumpf(packet, sizeof(struct etherbone_packet), "/tmp/packet.bin")

static int etherbone_check_header(struct etherbone_packet *req_packet);
static int etherbone_probe_response(struct etherbone_packet *resp_packet);
static int etherbone_process_packet(struct etherbone_memory_handlers *mem,
        struct etherbone_packet *req_packet, struct etherbone_packet *resp_packet);

int etherbone_callback(struct etherbone_memory_handlers *mem,
        uint8_t *buf, size_t buf_size, size_t recv_len)
{
    struct etherbone_packet *packet = NULL;
    size_t offset = 0;

    for (offset = 0; offset < recv_len; ++offset) {
        packet = (struct etherbone_packet *) (buf + offset);
        if (ntohs(packet->magic) == 0x4e6f) {
            break;
        }
        packet = NULL;
    }

    if (packet == NULL) {
        fprintf(stderr, "Could not find packet magic: recv_len=%lu\n", recv_len);
        DUMP((struct etherbone_packet *) buf);
        return -1;
    }

    size_t bytes_available = recv_len - offset;
    if (bytes_available < ETHERBONE_HEADER_LENGTH) {
        fprintf(stderr, "Not enought bytes for EtherBone header: available=%lu\n", bytes_available);
        DUMP(packet);
        return -1;
    }

    size_t packet_len = ETHERBONE_HEADER_LENGTH;
    if (packet->pf == 0) {
        // non-probe request requests include record header and record data
        packet_len += ETHERBONE_RECORD_HEADER_LENGTH;
        if (packet->record_hdr.wcount) {
            packet_len += (1 + packet->record_hdr.wcount) * 4;
        }
        if (packet->record_hdr.rcount) {
            packet_len += (1 + packet->record_hdr.rcount) * 4;
        }
    }

    if (bytes_available < packet_len) {
        fprintf(stderr, "Received less bytes than packet_len: len=%lu, available=%lu\n",
                packet_len, bytes_available);
        DUMP(packet);
        return -1;
    }

    // store the request packet in a temporary buffer  // FIXME: no need to?
    struct etherbone_packet *req_packet = malloc(packet_len);
    if (req_packet == NULL) {
        fprintf(stderr, "Could not allocate buffer for packet: len=%lu\n", packet_len);
        DUMP(packet);
        return -1;
    }
    memcpy(req_packet, packet, packet_len);
    packet = req_packet;

    // ignore buf_size, as the response packet should never be longer than request packet
    (void) buf_size;

    // store response in buf
    int response_len = etherbone_process_packet(mem, packet, (struct etherbone_packet *) buf);

    free(req_packet);
    return response_len;
}

int etherbone_check_header(struct etherbone_packet *req_packet)
{
    // check that the packet header is ok
    if(ntohs(req_packet->magic) != 0x4e6f) {
        fprintf(stderr, "Wrong magic: 0x%04x\n", ntohs(req_packet->magic));
        DUMP(req_packet);
        return -1;
    }
    if(req_packet->version != 1) {
        fprintf(stderr, "Wrong version: %d\n", req_packet->version);
        DUMP(req_packet);
        return -1;
    }
    if(req_packet->addr_size != 4) {  /* 32 bits address */
        fprintf(stderr, "Wrong addr_size: %d\n", req_packet->addr_size);
        DUMP(req_packet);
        return -1;
    }
    if(req_packet->port_size != 4) {  /* 32 bits data */
        fprintf(stderr, "Wrong port_size: %d\n", req_packet->port_size);
        DUMP(req_packet);
        return -1;
    }
    return 0;
}

int etherbone_probe_response(struct etherbone_packet *resp_packet)
{
    resp_packet->magic = htons(0x4e6f);
    resp_packet->version = 1;
    resp_packet->nr = 1;
    resp_packet->pr = 1;
    resp_packet->pf = 0;
    resp_packet->addr_size = 4; // 32 bits
    resp_packet->port_size = 4; // 32 bits
    return 8;  // always 8 bytes
}

int etherbone_process_packet(struct etherbone_memory_handlers *mem,
        struct etherbone_packet *req_packet, struct etherbone_packet *resp_packet)
{
    if (etherbone_check_header(req_packet) != 0) {
        return -1;
    }

    // for probe requests we just send response
    if (req_packet->pf == 1) {
        return etherbone_probe_response(resp_packet);
    }

    uint32_t rcount = req_packet->record_hdr.rcount;
    uint32_t wcount = req_packet->record_hdr.wcount;
    uint32_t resp_len = 0;

    if(wcount > 0) {
        uint32_t addr = ntohl(req_packet->record_hdr.base_write_addr);
        for(uint32_t i = 0; i < wcount; i++) {
            uint32_t data = ntohl(req_packet->record[i].write_value);
            mem->write(mem->arg, addr, data);
            addr += 4;
        }
    }

    if(rcount > 0) {
        for(uint32_t i = 0; i < rcount; i++) {
            uint32_t addr = ntohl(req_packet->record[i].read_addr);
            uint32_t data = mem->read(mem->arg, addr);
            resp_packet->record[i].write_value = htonl(data);
        }
        resp_packet->magic = htons(0x4e6f);
        resp_packet->version = 1;
        resp_packet->nr = 1;
        resp_packet->pr = 0;
        resp_packet->pf = 0;
        resp_packet->addr_size = 4; // 32 bits
        resp_packet->port_size = 4; // 32 bits
        resp_packet->record_hdr.wcount = rcount;
        resp_packet->record_hdr.rcount = 0;
        // we don't convert with htonl, as we didn't convert it before with ntohl
        resp_packet->record_hdr.base_write_addr = req_packet->record_hdr.base_ret_addr;
        resp_len = sizeof(struct etherbone_packet) + rcount * sizeof(struct etherbone_record);
    }

    return resp_len;
}
