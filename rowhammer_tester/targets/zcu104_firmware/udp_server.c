#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <assert.h>

#include "udp_server.h"

struct udp_server {
    struct sockaddr_in addr;
    int socket_fd;
    char *buf;
};

int udp_server_run(void *arg, udp_server_callback callback, int port, size_t buf_size) {
    struct udp_server server = {0};

    // allocate buffer
    if ((server.buf = malloc(buf_size)) == NULL) {
        perror("Failed to allocate buffer");
        goto error;
    }

    // open socket
    if ((server.socket_fd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("Could not open socket");
        goto error;
    }

    // bind address
    memset(&server.addr, 0, sizeof(server.addr));
    server.addr.sin_family = AF_INET;
    server.addr.sin_port = htons(port);
    server.addr.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(server.socket_fd, (struct sockaddr *) &server.addr, sizeof(server.addr)) < 0) {
        perror("Could not bind socket to port");
        goto error;
    }

    // start server loop
    printf("Serving on port %d ...\n", port);
    while (1) {
        // wait for a packet
        struct sockaddr_in src_addr = {0};
        socklen_t addr_len = sizeof(src_addr);
        int received_len = recvfrom(server.socket_fd, server.buf, buf_size, 0, (struct sockaddr *) &src_addr, &addr_len);
        if (received_len < 0) {
            perror("Failed to receive data from socket");
            goto error;
        }

        dbg_printf("Received %d byte packet\n", received_len);
        dbg_memdump(server.buf, received_len);

        // process the incoming data
        int response_len = callback(arg, server.buf, buf_size, received_len);
        if (response_len < 0) {
            fprintf(stderr, "Error while processing a packet from %s:%d\n",
                    inet_ntoa(src_addr.sin_addr), ntohs(src_addr.sin_port));
            goto error;
        }

        // do not respond if there is no response data?
        if (response_len == 0)
            continue;

        // send the response
        dbg_printf("Sending %d byte response\n", response_len);
        dbg_memdump(server.buf, response_len);

        if (sendto(server.socket_fd, server.buf, response_len, 0, (struct sockaddr *) &src_addr, addr_len) == -1) {
            char msg[100];
            sprintf(msg, "Failed to reply to %s:%d", inet_ntoa(src_addr.sin_addr), ntohs(src_addr.sin_port));
            perror(msg);
            goto error;
        }
    }

    assert(0);  // should never get here

error:
    printf("Aborting\n");
    if (server.socket_fd > 0) {
        close(server.socket_fd);
    }
    if (server.buf != NULL) {
        free(server.buf);
    }
    return -1;
}
