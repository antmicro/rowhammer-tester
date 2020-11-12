from litex.tools.litex_server import RemoteServer

def litex_srv():
    from litex.tools.remote.comm_udp import CommUDP
    udp_ip = '192.168.100.50'
    udp_port = 1234
    comm = CommUDP(udp_ip, udp_port, debug=False)

    server = RemoteServer(comm, '127.0.0.1', 1234)
    server.open()
    server.start(4)
