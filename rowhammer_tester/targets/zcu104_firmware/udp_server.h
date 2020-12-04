#ifndef UDP_SERVER_H
#define UDP_SERVER_H

// Callback function called on incoming packets
//
// It passes the number of bytes received (recv_len) and the buffer with the data.
// The callback should process the packet, write response to the buffer (at most
// buf_size bytes) and return number of response bytes written to be sent as reply.
// It can return -1 to signalize an error and terminate the server.
typedef int (*udp_server_callback)(char *buf, size_t buf_size, size_t recv_len);

int udp_server_run(int port, size_t buf_size, udp_server_callback callback);

#endif /* UDP_SERVER_H */
