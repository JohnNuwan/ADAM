
import socket
import struct

def get_network_info(ip_address):
    packed_ip = socket.inet_aton(ip_address)
    unpacked_ip = struct.unpack("!L", packed_ip)[0]
    return unpacked_ip

def recognize_network(ip_address, subnet_mask):
    ip_num = get_network_info(ip_address)
    mask_num = get_network_info(subnet_mask)
    network_id = ip_num & mask_num
    return socket.inet_ntoa(struct.pack('!L', network_id))

if __name__ == '__main__':
    ip_address = "192.168.1.1"
    subnet_mask = "255.255.255.0"
    print(recognize_network(ip_address, subnet_mask))
