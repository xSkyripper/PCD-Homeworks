import abc
import socket
import click
import math
import time
import utils


SERVER_IP = '127.0.0.1'
SERVER_PORT = 8008

class TestClient(abc.ABC):
    @abc.abstractmethod
    def basic_send_data(self, data):
        pass

    @abc.abstractmethod
    def basic_recv_data(self, chunk_size):
        pass

    @abc.abstractmethod    
    def send_data(self, data):
        self.basic_send_data(data)
        self.handle_stop_and_wait_send()

    @abc.abstractmethod
    def recv_data(self, chunk_size):
        data, addr = self.basic_recv_data(chunk_size)
        self.handle_stop_and_wait_recv()
        return data, addr

    @abc.abstractmethod
    def handle_stop_and_wait_send(self):
        if not self.stop_and_wait:
            return
        # print("Waiting an ack {}".format(time.time()))
        pack, addr = self.basic_recv_data(3)
        ack = utils.unpack_values(pack, '3s')[0].decode()
        assert ack == 'ACK'
        # print ("Received an ack")

    @abc.abstractmethod
    def handle_stop_and_wait_recv(self):
        if not self.stop_and_wait:
            return
        # print("Sending ack {}".format(time.time()))
        pack = utils.pack_values(('ACK'.encode('UTF-8'),), '3s')
        self.basic_send_data(pack)
        # print("Sent an ack {}".format(time.time()))



    @abc.abstractmethod
    def send_file(self, file, chunk_size):
        pack = utils.pack_values(('INIT'.encode('UTF-8'),),'4s')
        self.basic_send_data(pack)

        # print('[CLIENT] Sending chunk size ...')
        pack = utils.pack_values((chunk_size,), 'I')
        self.send_data(pack)
        print('[CLIENT] Sent {} chunk size to {}'.format(chunk_size, self.addr))

        # print('[CLIENT] Sending file {} to {} ...'.format(file, self.addr))
        with open(file, "rb") as f:
            file_data = f.read()
            file_data_size = len(file_data)

            # print('[CLIENT] Sending chunks count ...')
            chunks_count = math.ceil(file_data_size / chunk_size)
            pack = utils.pack_values((chunks_count,), 'I')
            self.send_data(pack)
            print('[CLIENT] Sent {} chunks count to {}'.format(chunks_count, self.addr))

            # print('[CLIENT] Sending file data size ...')
            pack = utils.pack_values((file_data_size,), 'I')
            self.send_data(pack)
            print('[CLIENT] Sent {} file data size to {}'.format(file_data_size, self.addr))

            sent_chunks_count = 0
            sent_size = 0
            for chunk_index in range(0, chunks_count):
                # print('[CLIENT] Sending chunk {} ...'.format(chunk_index))
                chunk = file_data[chunk_index * chunk_size : (chunk_index +  1) * chunk_size]
                sent_size += len(chunk)
                self.send_data(chunk)
                sent_chunks_count += 1
                # print("[CLIENT] Sent chunk {}".format(chunk_index))
        
        return chunk_size, sent_chunks_count, chunks_count, sent_size
                

class TCPTestClient(TestClient):
    def __init__(self, ip=SERVER_IP, port=SERVER_PORT, stop_and_wait=False):
        self.addr = (ip, port)
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serv.connect(self.addr)
        self.stop_and_wait = stop_and_wait
        

    def basic_send_data(self, data):
        self.serv.send(data)

    def basic_recv_data(self, chunk_size):
        data = self.serv.recv(chunk_size)
        return data, None

    def send_data(self, data):
        super().send_data(data)

    def recv_data(self, chunk_size):
        return super().recv_data(chunk_size)

    def handle_stop_and_wait_send(self):
        super().handle_stop_and_wait_send()

    def handle_stop_and_wait_recv(self):
        super().handle_stop_and_wait_recv()

    def send_file(self, file, chunk_size):
        return super().send_file(file=file, chunk_size=chunk_size)


class UDPTestClient(TestClient):
    def __init__(self, ip=SERVER_IP, port=SERVER_PORT, stop_and_wait=False):
        self.addr = (ip, port)
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.stop_and_wait = stop_and_wait

    def basic_send_data(self, data):
        self.serv.sendto(data, self.addr)
    
    def basic_recv_data(self, chunk_size):
        data, addr = self.serv.recvfrom(chunk_size)
        return data, addr

    def send_data(self, data):
        super().send_data(data)

    def recv_data(self, chunk_size):
        return super().recv_data(chunk_size)

    def handle_stop_and_wait_send(self):
        super().handle_stop_and_wait_send()

    def handle_stop_and_wait_recv(self):
        super().handle_stop_and_wait_recv()

    def send_file(self, file, chunk_size):
        return super().send_file(file=file, chunk_size=chunk_size)


cls_client = {
    'tcp': TCPTestClient,
    'udp': UDPTestClient
}


@click.command()
@click.option('--protocol', type=click.Choice(['tcp', 'udp']), help="Protocol of the client")
@click.option('--chunk-size', type=click.IntRange(1, 65536), default=1024, help="The chunk size of the transfer")
@click.option('--ip', default=SERVER_IP, help="IPv4 of the server")
@click.option('--port', default=SERVER_PORT, type=click.INT, help="Port of the server process")
@click.option('--file', required=True, help='File to be sent')
@click.option('--stop-and-wait', is_flag=True, help="Use the stop-and-wait mechanism")
def start_transfer(protocol, chunk_size, ip, port, file, stop_and_wait):
    """ Benchmark client """

    client_class = cls_client[protocol]
    client = client_class(ip=ip, port=port, stop_and_wait=stop_and_wait)
    print('[CLIENT] Started client {}, chunk size {} for server {}:{} ... '.format(protocol, chunk_size, ip, port))

    start_time = time.time()
    chunk_size, sent_chunks_count, chunks_count, sent_size = client.send_file(file, chunk_size)
    end_time = time.time()
    delta_time = float(end_time) - start_time

    print('Out: PROTOCOL, CHUNK_SIZE, SENT_CHUNKS, TOTAL_CHUNKS, SENT_BYTES, TIME')
    print('Out: {}, {}, {}, {}, {}, {}\n'.format(
                    protocol,
                    chunk_size,
                    sent_chunks_count,
                    chunks_count,
                    sent_size,
                    delta_time,
                    ))

if __name__ == '__main__':
    start_transfer()