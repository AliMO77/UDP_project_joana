
import socket
import os
import math
import threading
import time
import logging
logging.basicConfig(level=logging.INFO)
import hashlib
import sys
import traceback
import random

class ClientInfo:
    def __init__(self, client_id, total_clients, window_size,probability):
        self.client_id = client_id
        self.total_clients = total_clients
        self.window_size = window_size
        self.probability = probability

        self.acknowledged_frame = -1
        self.retransmissions = 0
        self.last_ack_time = time.time()
        self.sent_eof = False
        self.sent_frames = set()
        self.next_seq_num = 0
        self.acked_frames = set()



class FileServer:

    file_path= "./myfile.txt"
    udp_payload_size = 4096
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
        
        self.bytes_sent = 0
        self.bytes_received = 0
        

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
    
    
    def update_client_info(self, address, client_id, total_clients, window_size,probability):
            with self.clients_lock:  # Acquire the lock before updating
                if address not in self.clients:
                    self.clients[address] = ClientInfo(client_id, total_clients, window_size,probability)
                else :
                    client_info = self.clients[address]
                    client_info.client_id = client_id
                    client_info.total_clients = total_clients
                    client_info.window_size = window_size
                    client_info.probability =probability

   
    def safe_sendto_inwindow(self, frames,base,r=None):
        try:
            # Send frames in the window
            with self.clients_lock:
                for client_address in self.clients:
                    if random.random() > self.clients[client_address].probability:
                        window_size = self.clients[client_address].window_size  
                        next_seq_num = self.clients[client_address].acknowledged_frame+1 
                        if next_seq_num < 0:
                            next_seq_num=0
                        end_seq_num = min(next_seq_num + window_size, len(frames))
                    
                        # print('client: ',self.clients[client_address].client_id, 
                        #       'next_seq_num: ',next_seq_num,
                        #       'end_seq_num: ',end_seq_num,'all_acked_frames: ',self.clients[client_address].acked_frames) 
                        
                        while next_seq_num < end_seq_num :
                            if next_seq_num not in self.clients[client_address].acked_frames:
                                
                                seq_str = str(next_seq_num).zfill(self.seq_number_size).encode()
                                frame = seq_str + frames[next_seq_num]
                                self.send_sock.sendto(frame, client_address)
                                #print(f"\r\nSent frame {next_seq_num} to Client {self.clients[client_address].client_id} with win_size: {window_size}",end='',flush=True)
                                self.clients[client_address].sent_frames.add(next_seq_num)
                                self.bytes_sent += len(frame)
                                if r is not None:
                                    self.clients[client_address].retransmissions+=1
                                
                            next_seq_num += 1
                            
                        self.clients[client_address].next_seq_num = next_seq_num
  
        except Exception as e:
            print(f"Exception occured in function 'safe_sendto_inwindow', Failed to send data: {e}")
        return next_seq_num
        

    def update_aknowledgements(self,ack,ack_address):
       try:
            ack_content = ack.decode().split(',')
            if ack_content[0] == 'ack':
                ack_num = int(ack_content[1])
                ack_client_id = int(ack_content[2])
                # Update the highest acked frame for this client
                client = self.clients.get(ack_address)
                
                sent_eof = self.clients[ack_address].sent_eof
                last_ack =  self.clients[ack_address].acknowledged_frame
                sent_frames = self.clients[ack_address].sent_frames
                
                if client:
                    if ack_num in sent_frames and not sent_eof:              
                        self.clients[ack_address].acknowledged_frame = max(last_ack, ack_num)
                        self.clients[ack_address].acked_frames.add(ack_num)
                        #print(f"Received ACK {ack_num} from Client {ack_client_id}",flush=True)      

       except Exception as e:
            print(f"Exception occured in function 'update_aknowledgements', couldn't Received ACK: {e}")
    
    def find_global_min_ack(self):
        with self.clients_lock:
            min_acks = [client.acknowledged_frame for client in self.clients.values()]
        return min(min_acks) if min_acks else 0


    
    def handle_transmission(self):
        with open(self.file_path, "rb") as file:
            frames = [file.read(self.udp_payload_size - self.seq_number_size) for _ in range(self.num_frames)]
            try:
                # Initialize variables to keep track of frames and acknowledgments
                base = -1
              
                while base < len(frames)-1:
                    # Send frames in the window to all clients
                    self.safe_sendto_inwindow(frames,base) 
                    
                    base = self.find_global_min_ack()  # Update the base to the global minimum ACK
                    timeout_start = time.time()
                    
                    acked_frames = [client.acked_frames for client in self.clients.values()]
                    next = max(min(acked_frames),default=0)
                    acks = {client.client_id:client.acknowledged_frame for client in self.clients.values()}
                    next = base+1
                    print(f"\r\nbase: {base},\nnext: {next}\nclient_acks: {acks}",end='')
                    print('\n**************************************************************')
                    
                    while base < next:
                        ack, ack_address = self.recv_sock.recvfrom(1024)  # Set a timeout for receiving ACKs
                        self.bytes_received += len(ack)
                        self.update_aknowledgements(ack, ack_address)
                                                
                        
                        base = self.find_global_min_ack()
                        
                        if time.time() - timeout_start > 5:
                            print(f"\r\nTimeout occurred. Resending frames\n",end='',flush=True)
                            self.safe_sendto_inwindow(frames,base,r=1)
                
                acks = {client.client_id:client.acknowledged_frame for client in self.clients.values()}            
                print(f"\r\nbase: {base},\nlast_frame: {self.num_frames-1}\nlast_client_acks: {acks}",end='')
                print('\n**************************************************************')
                self.send_EOF_signal()
            
            except Exception as e :
                logging.error(f"Exception occurred in function 'handle_transmission': {e}")
                print(f"Exception occured in function 'handle_transmission' : {e}")
                traceback.print_exc()
            
  
    def handle_requests(self):
         # This is to handle individual client requests.
        # It could call handle_transmission or other methods as needed.
        self.handle_transmission()
    
    def send_EOF_signal(self):
        try:
            checksum = self.calculate_file_hash(self.file_path)
            eof_frame = f'EOF,{checksum}'
            with self.clients_lock:
                for client in self.clients:
                    if  self.clients[client].sent_eof == False:
                        self.send_sock.sendto(eof_frame.encode(), client)
                        self.bytes_sent+=len(eof_frame.encode())
                        print(f"Sent end-of-file signal to Client {self.clients[client].client_id}")
                        self.clients[client].sent_eof = True
                
        except Exception as e:
            print(f"Exception occured in function 'send_EOF_signal'{e}")
    
    def finish_threads(self):
        with self.clients_lock:
            for thread in self.active_threads:
                if thread.is_alive() and thread is not threading.currentThread():
                    thread.join()
            # Clear the list after all threads have joined
            self.active_threads.clear()
        print('All threads have been successfully joined and removed.')
        
    def listen(self):
        client_requests = []  # A list to store client requests
        start_time = None  # Initialize start time to track time elapsed to handle all requests
        try:
            while not self.shutdown_event.is_set():
                # Receive the client's request
                
                data, address = self.recv_sock.recvfrom(4096)  # Buffer size
                self.bytes_received += len(data)

                message_parts = data.decode().split(',')
                request = message_parts[0]  # extract request

                if not start_time:
                    start_time = time.time()  # Start the timer when the first request is received

        
                # when client sends a message 'request_file'
                if request == 'request_file':
                    # Extract the rest of the details from the message
                    _, client_id, total_clients, filename, window_size,probability = message_parts[0],message_parts[1], message_parts[2], message_parts[3], message_parts[4], message_parts[5]

                    client_id = int(client_id.split('=')[1])
                    total_clients = int(total_clients.split('=')[1])
                    filename = str(filename.split('=')[1])
                    window_size = int(window_size.split('=')[1])
                    probability = float(probability.split('=')[1])
                    
                    client_requests.append((address, client_id, total_clients, filename, window_size))
                    self.update_client_info(address, client_id, total_clients, window_size,probability)

                    print(f"Received message: {request} from Client {client_id}. Total  requests collected: {len(client_requests)}")
                    

                    if len(client_requests) == total_clients:
                        
                        print("\nAll client requests received. Starting to handle requests.\n")
                        print("================================ [ BEGIN ] ================================ ✨\n")
                        for client in self.clients.values():
                            print(f"window size of client {client.client_id}: {client.window_size}, loss probability:{client.probability} ")
                        print("\n====================\n")
                        #for request in client_requests:
                            # Create a new thread for each client request
                        client_thread = threading.Thread(target=self.handle_requests, args=())
                        self.active_threads.append(client_thread)
                        client_thread.start()


                if data.decode() == 'EOR':
                    self.finish_threads()
                    end_time = time.time()  # Stop the timer 
                    total_time = end_time - start_time  # Calculate total time taken
                    print("================================ [ THE END ] ================================ ✨")
                    print(f"\nTransmissions completed, Total time taken to handle requests: {total_time:.2f} seconds.")
                    suming = []
                    for client in self.clients.values():
                        print(f"\nTotal retransmissions for client {client.client_id}: {client.retransmissions}")
                        suming.append(client.retransmissions)
                    
                    suming = sum(suming) 
                    print(f"\nTotal retransmissions for All clients: {suming}")

                    print(f"\nTotal data sent: {self.bytes_sent} bytes")
                    print(f"\nTotal data received: {self.bytes_received} bytes")
                    print(f"\nTotal bandwith: {self.bytes_received+self.bytes_sent} bytes")
                   
    
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