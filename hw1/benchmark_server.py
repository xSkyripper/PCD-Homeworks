import abc
import socket
import click
import select
import utils
import time

SERVER_IP = '127.0.0.1'
SERVER_PORT = 8008
SERVER_LISTEN_SIZE = 1
SERVER_TIMEOUT = 10

class TestServer(abc.ABC):
    @abc.abstractmethod
    def basic_send_data(self, data, peer):
        pass
    
    @abc.abstractmethod
    def basic_recv_data(self, chunk_size, peer):
        pass

    @abc.abstractmethod    
    def send_data(self, data, peer):
        self.basic_send_data(data, peer)
        self.handle_stop_and_wait_send(peer)

    @abc.abstractmethod
    def recv_data(self, chunk_size, peer):
        data, addr = self.basic_recv_data(chunk_size, peer)
        self.handle_stop_and_wait_recv(peer)

        return data, addr

    @abc.abstractmethod
    def handle_stop_and_wait_send(self, peer):
        if not self.stop_and_wait:
            return
        # print("Waiting an ack {}".format(time.time()))
        pack, addr = self.basic_recv_data(3, peer)
        ack = utils.unpack_values(pack, '3s')[0].decode()
        assert ack == 'ACK'
        # print ("Received ACK")

    @abc.abstractmethod
    def handle_stop_and_wait_recv(self, peer):
        if not self.stop_and_wait:
            return
        # print("Sending ack {}".format(time.time()))
        pack = utils.pack_values(('ACK'.encode('UTF-8'),), '3s')
        self.basic_send_data(pack, peer)
        # print("Sent an ack {}".format(time.time()))

    @abc.abstractmethod
    def recv_file(self, client, client_addr, file_path):
        # print("[SERVER] Receiving chunk size ...")
        pack, addr = self.basic_recv_data(4, client)
        init = utils.unpack_values(pack, '4s')[0].decode()
        assert init == 'INIT'
        if not client:
            client = addr
            peer_addr = addr
        else:
            peer_addr = client.getpeername()
        print("[SERVER] Receiving data from {}".format(client_addr or addr))    

        pack, addr = self.recv_data(4, client)
        chunk_size = utils.unpack_values(pack, 'I')[0]
        print("[SERVER] {} chunk size with {}".format(chunk_size, client_addr or addr))

        # print("[SERVER] Receiving chunk count ...")
        pack, addr = self.recv_data(4, client)
        chunk_count = utils.unpack_values(pack, 'I')[0]
        print("[SERVER] {} chunk count with {}".format(chunk_count, client_addr or addr))

        # print("[SERVER] Receiving file data size ...")
        pack, addr = self.recv_data(4, client)
        file_data_size = utils.unpack_values(pack, 'I')[0]
        print("[SERVER] {} file data size with {}".format(file_data_size, client_addr or addr))
        
        received_chunks_count = 0
        received_size = 0
        file_data_chunks = []
        try:
            for chunk_index in range(0, chunk_count):
                # print("[CLIENT] Receiving chunk {}...".format(chunk_index))
                data_chunk, addr = self.recv_data(chunk_size, client)
                # print("[CLIENT] Received chunk {}".format(chunk_index))
                received_chunks_count += 1
                received_size += len(data_chunk)
                # file_data_chunks.append(data_chunk)
        except socket.timeout:
            print('[SERVER] Socket timeout ... ')

        print('[SERVER] Received {}/{} chunks'.format(received_chunks_count, chunk_count))

        with open(file_path, 'wb') as f:
            for chunk in file_data_chunks:
                f.write(chunk)

        print("[SERVER] Finished.")

        return (peer_addr, chunk_size, received_chunks_count, chunk_count, received_size)
    
    @abc.abstractmethod
    def run(self):
        pass


class TCPTestServer(TestServer):
    def __init__(
        self,
        ip=SERVER_IP,
        port=SERVER_PORT,
        listen_size=SERVER_LISTEN_SIZE,
        stop_and_wait=False
        ):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(self.addr)
        self.sock.listen(listen_size)
        self.stop_and_wait = stop_and_wait

    def basic_send_data(self, data, peer):
        peer.send(data)
    
    def basic_recv_data(self, chunk_size, peer):
        data = peer.recv(chunk_size)
        return data, None

    def send_data(self, data, peer):
        super().send_data(data, peer)

    def recv_data(self, chunk_size, peer):
        return super().recv_data(chunk_size, peer)

    def handle_stop_and_wait_send(self, peer):
        super().handle_stop_and_wait_send(peer)

    def handle_stop_and_wait_recv(self, peer):
        super().handle_stop_and_wait_recv(peer)

    def recv_file(self, client, file_path):
        client_addr = client.getpeername()
        return super().recv_file(client=client, client_addr=client_addr, file_path=file_path)

    def run(self):
        print("[SERVER-TCP] Started server on port {}".format(self.addr[1]))

        while True:
            try:
                client, client_addr = self.sock.accept()
                print("[SERVER-TCP] {} connected".format(client_addr))
                res = self.benchmark_transfer(client)
                with open('server_logs.txt', 'a+') as f:
                    f.write('tcp, {}:{}, {}, {}, {}, {}, {}\n'.format(
                        res['peer_addr'][0],
                        res['peer_addr'][1],
                        res['chunk_size'],
                        res['received_chunks_count'],
                        res['chunk_count'],
                        res['received_size'],
                        res['transfer_time']
                        ))
                client.close()
                print("[SERVER-TCP] {} disconnected".format(client_addr))
            except socket.timeout:
                pass


        self.sock.close()
        print("[SERVER-TCP] {} closed".format(client_addr))
  
    def benchmark_transfer(self, client):
        start_time = time.time()
        peer_addr, chunk_size, received_chunks_count, chunk_count, received_size = self.recv_file(client=client, file_path='received.bin')
        end_time = time.time()
        delta_time = float(end_time) - start_time

        return {
            'peer_addr': peer_addr,
            'chunk_size': chunk_size,
            'received_chunks_count': received_chunks_count,
            'chunk_count': chunk_count,
            'received_size': received_size,
            'transfer_time': delta_time
        }


class UDPTestServer(TestServer):
    def __init__(
        self,
        ip=SERVER_IP,
        port=SERVER_PORT,
        listen_size=SERVER_LISTEN_SIZE,
        stop_and_wait=False
        ):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.addr)
        self.stop_and_wait = stop_and_wait

    def basic_send_data(self, data, peer):
        self.sock.sendto(data, peer)

    def basic_recv_data(self, chunk_size, peer):
        data, addr = self.sock.recvfrom(chunk_size)
        return data, addr

    def send_data(self, data, peer):
        super().send_data(data, peer)

    def recv_data(self, chunk_size, peer):
        self.sock.settimeout(SERVER_TIMEOUT)
        return super().recv_data(chunk_size, peer)

    def handle_stop_and_wait_send(self, peer):
        super().handle_stop_and_wait_send(peer)

    def handle_stop_and_wait_recv(self, peer):
        super().handle_stop_and_wait_recv(peer)

    def recv_file(self, file_path):
        return super().recv_file(client=None, client_addr=None, file_path=file_path)

    def run(self):
        print("[SERVER-UDP] Started server on port {}".format(self.addr[1]))
        
        while True:
            try:
                res = self.benchmark_transfer()
                with open('server_logs.txt', 'a+') as f:
                    f.write('udp, {}:{}, {}, {}, {}, {}, {}\n'.format(
                        res['peer_addr'][0],
                        res['peer_addr'][1],
                        res['chunk_size'],
                        res['received_chunks_count'],
                        res['chunk_count'],
                        res['received_size'],
                        res['transfer_time']
                        ))
                print('[SERVER-UDP] "Finished" with {}'.format(res['peer_addr']))
            except socket.timeout:
                pass
        
        self.sock.close()
        print("[SERVER-UDP] Sock closed")

    def benchmark_transfer(self):
        start_time = time.time()
        peer_addr, chunk_size, received_chunks_count, chunk_count, received_size = self.recv_file(file_path='received.bin')
        end_time = time.time()
        delta_time = float(end_time) - start_time

        return {
            'peer_addr': peer_addr,
            'chunk_size': chunk_size,
            'received_chunks_count': received_chunks_count,
            'chunk_count': chunk_count,
            'received_size': received_size,
            'transfer_time': delta_time
        }


cls_server = {
    'tcp': TCPTestServer,
    'udp': UDPTestServer
}
    

@click.command()
@click.option('--protocol', type=click.Choice(['tcp', 'udp']), help="Protocol of the server")
@click.option('--port', default=SERVER_PORT, help='Port of the server')
@click.option('--stop-and-wait', is_flag=True, help="Use the stop-and-wait mechanism")
def start_server(protocol, port, stop_and_wait):
    """ Benchmark server """

    server_class = cls_server[protocol]
    server = server_class(port=port, stop_and_wait=stop_and_wait)
    
    server.run()
    

if __name__ == '__main__':
    start_server()