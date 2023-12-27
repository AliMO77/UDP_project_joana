
import socket
import os
import math
import threading
import time
import logging
logging.basicConfig(level=logging.INFO)
import hashlib
import sys

class ClientInfo:
    def __init__(self, client_id, total_clients, window_size):
        self.client_id = client_id
        self.total_clients = total_clients
        self.window_size = window_size
        self.acknowledged_frame = -1
        self.retransmissions = 0
        self.last_ack_time = time.time()



class FileServer:

    file_path= "./myfile.txt"
    udp_payload_size = 16
    seq_number_size = 4
    total_process = None


    def __init__(self, server_ip='127.0.0.1', server_port=12345):
        self.server_ip = server_ip
        self.server_port = server_port
        # Create a UDP socket for sending data
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Create a UDP socket for receiving data and bind it
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind((self.server_ip, self.server_port))
        
        
        self.clients_lock = threading.Lock()

        print(f"Server started at {self.server_ip}:{self.server_port}")
        self.num_frames = self.file_fragements()
        self.clients = {}

        self.active_threads = []
        self.shutdown_event = threading.Event() 
        

    def calculate_file_hash(self,filename):
        hash_func = hashlib.sha256()  # You can choose other algorithms like MD5 or SHA-1
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def file_fragements(self):
        file_size = os.path.getsize(self.file_path)
        print(f"File size is {file_size} bytes")
        payload = self.udp_payload_size-self.seq_number_size
        print(f"UDP payload size {payload} bytes")
        num_frames = math.ceil(file_size / payload)
        print(f"Number of frames to send: {num_frames}")
        return num_frames
    
    
    def update_client_info(self, address, client_id, total_clients, window_size):
            with self.clients_lock:  # Acquire the lock before updating
                if address not in self.clients:
                    self.clients[address] = ClientInfo(client_id, total_clients, window_size)
                else :
                    client_info = self.clients[address]
                    client_info.client_id = client_id
                    client_info.total_clients = total_clients
                    client_info.window_size = window_size

    def send_EOF_signal(self):
        try:
            checksum = self.calculate_file_hash(self.file_path)
            eof_frame = f'EOF,{checksum}'
            with self.clients_lock:
                for client in self.clients:  
                    self.send_sock.sendto(eof_frame.encode(), client)
                    print(f"Sent end-of-file signal to Client {self.clients[client].client_id}")
        except Exception as e:
            print(f"Exception occured in function 'send_EOF_signal'{e}")
        

   
    def safe_sendto_inwindow(self, frames,window_size,base,next_seq_num):
        try:
            # Send frames in the window
            with self.clients_lock:
                while next_seq_num < (base + window_size) and next_seq_num < len(frames):
                    seq_str = str(next_seq_num).zfill(self.seq_number_size).encode()
                    frame = seq_str + frames[next_seq_num]
                    for client_address in self.clients:
                        self.send_sock.sendto(frame, client_address)
                        print(f"Sent frame {next_seq_num} to Client {self.clients[client_address].client_id}")
                    next_seq_num += 1
                    
        except Exception as e:
            print(f"Exception occured in function 'safe_sendto_inwindow', Failed to send data: {e}")
        return next_seq_num
        

    def update_aknowledgements(self,ack,client_acks):
       try:
            ack_content = ack.decode().split(',')
            if ack_content[0] == 'ack':
                ack_num = int(ack_content[1])
                ack_client_id = int(ack_content[2])
                # Update the highest acked frame for this client
                if ack_client_id in  [client.client_id for client in self.clients.values()]:     
                    client_acks[ack_client_id] = max(client_acks[ack_client_id], ack_num)
                    print(f"Received ACK {ack_num} from Client {ack_client_id}")      
       except Exception as e:
            print(f"Exception occured in function 'update_aknowledgements', couldn't Received ACK: {e}")
    
    def find_next_base(self,client_acks, current_base, max_frame):
        print(f"base was at {current_base}")
        while current_base < max_frame and all(ack >= current_base for ack in client_acks.values()):
            current_base += 1
        print(f"base moved to {current_base}")
        return current_base

    
    def handle_transmission(self, address, id_process, total_process, filename, window_size):
        with open(self.file_path, "rb") as file:
            frames = [file.read(self.udp_payload_size - self.seq_number_size) for _ in range(self.num_frames)]
            try:
                # Initialize variables to keep track of frames and acknowledgments
                base = 0
                next_seq_num = 0
                client_acks = {client.client_id: client.acknowledged_frame  for client in self.clients.values()}  # Track the highest acked frame per client
                
                while base < len(frames)-1:
                    # Send frames in the window to all clients
                    next_seq_num = self.safe_sendto_inwindow(frames,window_size,base,next_seq_num) 

                # Wait for acknowledgments from all clients for frames in the window
                    while base < next_seq_num and not all(ack >= base for ack in client_acks.values()):
                            ack, ack_address = self.recv_sock.recvfrom(1024)
                            self.update_aknowledgements(ack,client_acks)
                                        
                            #if timeout resend frames in window
                            if time.time() - self.clients[ack_address].last_ack_time > 5:
                                print(f"Timeout occurred. Resending frames from {base} to {next_seq_num - 1}")
                                for i in range(base, next_seq_num):
                                    seq_str = str(i).zfill(self.seq_number_size).encode()
                                    frame = seq_str + frames[i]
                                    for client_address in self.clients:
                                        self.send_sock.sendto(frame, client_address)
                                        print(f"Resent frame {i} to {self.clients[client_address].client_id}")  
                                        self.clients[client_address].last_ack_time=time.time()
                    base = min(client_acks.values())
                self.send_EOF_signal()
            
            except Exception as e :
                print(f"Exception occured in function 'handle_transmission' : {e}")
            finally:
                # Safely removing the thread from the active list
                with self.clients_lock:  # Assuming this lock is for all critical sections
                    if threading.current_thread() in self.active_threads:
                        self.active_threads.remove(threading.current_thread())
               
  
    def handle_requests(self,address, client_id, total_clients, filename, window_size):
         # This is to handle individual client requests.
        # It could call handle_transmission or other methods as needed.
        self.handle_transmission(address, client_id, total_clients, filename, window_size)
        
    def listen(self):
        client_requests = []  # A list to store client requests
        start_time = None  # Initialize start time to track time elapsed to handle all requests
        try:
            while not self.shutdown_event.is_set():
                # Receive the client's request
                
                data, address = self.recv_sock.recvfrom(4096)  # Buffer size

                message_parts = data.decode().split(',')
                request = message_parts[0]  # extract request

                if not start_time:
                    start_time = time.time()  # Start the timer when the first request is received

        
                # when client sends a message 'request_file'
                if request == 'request_file':
                    # Extract the rest of the details from the message
                    _, client_id, total_clients, filename, window_size = message_parts[0], message_parts[1], message_parts[2], message_parts[3], message_parts[4]

                    client_id = int(client_id.split('=')[1])
                    total_clients = int(total_clients.split('=')[1])
                    filename = str(filename.split('=')[1])
                    window_size = int(window_size.split('=')[1])
                    
                    client_requests.append((address, client_id, total_clients, filename, window_size))
                    self.update_client_info(address, client_id, total_clients, window_size)

                    print(f"Received message: {request} from Client {client_id}. Total  requests collected: {len(client_requests)}")
                    

                    if len(client_requests) == total_clients:
                        
                        print("\nAll client requests received. Starting to handle requests.\n")
                        print("================================ [ BEGIN ] ================================ ✨\n")
                        for client in self.clients.values():
                            print(f"window size of client {client.client_id}: {client.window_size}")
                        print("\n====================\n")
                        for request in client_requests:
                            # Create a new thread for each client request
                            address, client_id, total_clients, filename, window_size = request
                            client_thread = threading.Thread(target=self.handle_requests, args=(address, client_id, total_clients, filename, window_size))
                            self.active_threads.append(client_thread)
                            client_thread.start() 
                            
                        
                if data.decode() == 'EOR':
                    end_time = time.time()  # Stop the timer 
                    total_time = end_time - start_time  # Calculate total time taken
                    print("================================ [ THE END ] ================================ ✨")
                    print(f"\nTransmissions completed, Total time taken to handle requests: {total_time:.2f} seconds.")
                    suming = []
                    for client in self.clients.values():
                        print(f"\nTotal retransmissions for client {client.client_id}: {client.retransmissions}")
                        suming.append(client.retransmissions)
                    
                    suming = sum(suming) 
                    print(f"\nTotal retransmissions for All clients {suming}")
                   
    
        except Exception as e:
            print(f"An error occurred in listening Server : {e}")
        finally:
        # Wait for all threads to complete before closing sockets 
           
            for thread in threading.enumerate():
                if thread is not threading.currentThread():
                    thread.join()
                
            print(f"Sayonara")
            
            end_time = time.time()  # Stop the timer 
            total_time = end_time - start_time  # Calculate total time taken

            print(f"\nServer shut down gracefully. Total running time: {total_time:.2f} seconds.")

            self.send_sock.close()
            self.recv_sock.close()


# To run the server
if __name__ == "__main__":
    server = FileServer()  # You can specify IP and port here if needed
    try:
        server.listen()
    except KeyboardInterrupt:
        server.shutdown_event.set()  # Signal the server to shut down