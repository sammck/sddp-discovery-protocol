#!/usr/bin/env python3

import socket

#msg = \
#    'SEARCH * HTTP/1.0\r\n' \
#    'Host: 239.255.255.250:1902\r\n' \
#    '\r\n'

msg = \
    'SEARCH * SDDP/1.0\r\n' \
    'Host: "239.255.255.250:1902"\r\n' \
    'Debug: "True"\r\n' \
    '\r\n'

# Set up UDP socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.settimeout(2)
s.sendto(msg.encode('utf-8'), ('239.255.255.250', 1902) )

try:
    while True:
        data, addr = s.recvfrom(65507)
        print(addr, data.decode('utf-8'))
except socket.timeout:
    pass





