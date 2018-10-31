import socket
import random
import select
import threading

LENGTH_SEQUENCE = 256   # 序列号有效范围 0~255
RECEIVE_WINDOW = 128    # 接收窗口大小(SR协议中使用)
SEND_WINDOW = 128   # 发送窗口大小

MAX_TIMER = 3   # 计时器最大超时时间

SERVER_PORT_1 = 12138
SERVER_PORT_2 = 12139

CLIENT_PORT_1 = 12140
CLIENT_PORT_2 = 12141

SERVER_IP = '127.0.0.1'
CLIENT_IP = '127.0.0.1'

BUFFER_SIZE = 2048  # 缓存大小


def make_pkt(next_seq_num, data):
    """数据帧格式
     SEQ' 'data
     """
    pkt_s = str(next_seq_num) + ' ' + str(data)
    return pkt_s.encode()


def make_ack_pkt(ack_num):
    """ACK帧格式
    ACK' 'ack_num
    """
    return ('ACK ' + str(ack_num)).encode()


class GBNClient(object):
    def __init__(self):
        self.base = 0
        self.next_seq_num = 0
        self.SEND_WINDOW = SEND_WINDOW
        self.timer = 0
        self.socket_1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # 主要用作Client作为发送端的socket
        self.socket_1.bind(('', CLIENT_PORT_1))
        self.socket_2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # 主要用作Client作为接收端的socket
        self.socket_2.bind(('', CLIENT_PORT_2))
        self.data_seq = [b'0'] * LENGTH_SEQUENCE    # 作为已发送数据的缓存

    def begin(self):
        while True:
            while self.next_seq_num < self.base + self.SEND_WINDOW:
                pkt = make_pkt(self.next_seq_num, str(self.next_seq_num + LENGTH_SEQUENCE))
                if self.next_seq_num == self.base:
                    self.timer = 0
                self.socket_1.sendto(pkt, (SERVER_IP, SERVER_PORT_1))
                print("Send", self.next_seq_num)
                self.data_seq[self.next_seq_num] = pkt
                self.next_seq_num = (self.next_seq_num + 1) % LENGTH_SEQUENCE
                if self.next_seq_num == 0:
                    return  # 用作测试 仅发送一轮
            readable, writeable, errors = select.select([self.socket_1, ], [], [], 1)
            # 非阻塞方式
            if len(readable) > 0:
                mgs_byte, address = self.socket_1.recvfrom(BUFFER_SIZE)
                message = mgs_byte.decode()
                if 'ACK' in message:
                    messages = message.split()
                    print("Receive", message)
                    self.base = int(messages[1])
                    if self.base == self.next_seq_num:
                        self.timer = -1
                    else:
                        self.timer = 0
            else:
                # 如果没有收到ACK 则将定时器加1
                self.timer += 1
                if self.timer > MAX_TIMER:
                    self.timer = 0
                    for i in range(self.base,
                                   self.next_seq_num if self.next_seq_num > self.base
                                   else self.next_seq_num + LENGTH_SEQUENCE):
                        # 用于序列号使用的处理
                        self.socket_1.sendto(self.data_seq[i % LENGTH_SEQUENCE], (SERVER_IP, SERVER_PORT_1))
                        print("Resend", self.data_seq[i % LENGTH_SEQUENCE])


class GBNServer(object):
    def __init__(self):
        self.base = 0
        self.expected_seq_num = 0
        self.SEND_WINDOW = SEND_WINDOW
        # self.RECEIVE_WINDOW = RECEIVE_WINDOW
        # 暂未使用 GBN协议中作为接收端的接收窗口大小为1
        self.timer = 0
        self.socket_1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # 主要用作Server作为接收端的socket
        self.socket_1.bind(('', SERVER_PORT_1))
        self.socket_2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # 主要用作Server作为发送端的socket
        self.socket_2.bind(('', SERVER_PORT_2))
        self.data_seq = [b'0'] * LENGTH_SEQUENCE    # 接收数据

    def __recv(self):
        readable, writeable, errors = select.select([self.socket_1, ], [], [], 1)
        if len(readable) > 0:
            mgs_byte, address = self.socket_1.recvfrom(BUFFER_SIZE)
            message = mgs_byte.decode().split()
            if int(message[0]) == self.expected_seq_num:
                self.data_seq[self.expected_seq_num] = message[1]
                ack_pkt = make_ack_pkt(self.expected_seq_num)
                self.socket_1.sendto(ack_pkt, (CLIENT_IP, CLIENT_PORT_1))
                print("Send ACK", self.expected_seq_num)
                self.expected_seq_num = (self.expected_seq_num + 1) % LENGTH_SEQUENCE
            else:
                ack_pkt = make_ack_pkt(self.expected_seq_num)
                self.socket_1.sendto(ack_pkt, (CLIENT_IP, CLIENT_PORT_1))
                print("ReSend ACK", self.expected_seq_num)

    def begin(self):
        while True:
            self.__recv()
            if self.expected_seq_num == 0:
                break   # 用作测试 仅发送一轮
        for i in range(LENGTH_SEQUENCE):
            print(i, self.data_seq[i])

# TODO 模拟丢包实现
# TODO 全双工通信实现
# TODO SR协议实现


def main():
    client = GBNClient()
    server = GBNServer()
    client_thread = threading.Thread(target=client.begin)
    server_thread = threading.Thread(target=server.begin)
    server_thread.start()
    client_thread.start()


if __name__ == '__main__':
    main()
