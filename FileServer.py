
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
        
        

    def log_error(self, message):
        logging.error(message)

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

   
    def safe_sendto(self, data, address):
        try:
            self.send_sock.sendto(data, address)
        except Exception as e:
            print(f"Failed to send data to {address}: {e}")

    def handle_transmission(self, address, id_process, total_process, filename, window_size):
        print(f"window size of client {id_process} to Client {window_size}")
        with open(self.file_path, "rb") as file:
            frames = [file.read(self.udp_payload_size - self.seq_number_size) for _ in range(self.num_frames)]
            
            # Initialize window variables
            window_start = 0
            window_end = min(window_start + window_size - 1, len(frames) - 1)

            # Send initial window of frames
            for current_frame in range(window_start, min(window_end + 1, len(frames))):
                seq_str = str(current_frame).zfill(self.seq_number_size).encode()
                frame = seq_str + frames[current_frame]
                self.safe_sendto(frame, address)
                print(f"#Sent frame {current_frame} to Client {id_process}")
            print(f"**************")
                
            sent_frames = set(range(window_start, min(window_end + 1, len(frames))))
            while window_start < len(frames)-1:
                
                # Gather ACKs from all clients
                acks = [client_info.acknowledged_frame for client_info in self.clients.values()]
                min_ack = min(acks) if acks else -1
               
                window_end = min(window_start + window_size - 1, len(frames) - 1)
                
                # Slide window and send new frames if ACKs received
                if min_ack >= window_start:
                    print(f'******************************client {id_process} window was at : [{window_start},{window_end}]')
                    window_start = min_ack + 1
                    window_end = min(window_start + window_size - 1, len(frames) - 1)
                    
                    for current_frame in range(window_start, min(window_end + 1, len(frames))):
                        seq_str = str(current_frame).zfill(self.seq_number_size).encode()
                        frame = seq_str + frames[current_frame]
                        self.safe_sendto(frame, address)
                        sent_frames.add(current_frame)  # Add to sent frames   
                        print(f'******************************client {id_process} window moved to : [{window_start},{window_end}]')
                        print(f"\n#Sent frame {current_frame} to Client {id_process}")
                        
                #wait for acks
                timeout_start = time.time()
                print('waiting acks for frames: ',sent_frames)
                try:
                    while not all(ack >= min(sent_frames, default=-1) for ack in acks):

                        ack, ack_address = self.recv_sock.recvfrom(1024)
                        ack_content = ack.decode().split(',')

                        ack_num = int(ack_content[1])
                        ack_client_id = int(ack_content[2])

                        if ack_content[0] == 'ack' and ack_num in sent_frames:
                            print(f"\n---Received ACK {ack_num} from Client {ack_client_id}")
                            with self.clients_lock:
                                if ack_address in self.clients:
                                    self.clients[ack_address].acknowledged_frame = ack_num 
                                    print(f"---Client {ack_client_id}'s last acknowledged frame updated to {ack_num}\n")
                                    # Efficiently discard frames up to the acknowledged one
                                    # sent_frames.discard(ack_num)
                                    frames_to_discard = {frame for frame in sent_frames if frame <= ack_num}
                                    sent_frames.difference_update(frames_to_discard)   
                        
                        requested_frame = int(ack_content[1])
                        if ack_content[0] == 'retransmit' and requested_frame in sent_frames:
                            if 0 <= requested_frame < len(frames):
                                # Prepare and send the requested frame
                                seq_str = str(requested_frame).zfill(self.seq_number_size).encode()
                                frame_to_retransmit = seq_str + frames[requested_frame]
                                self.safe_sendto(frame_to_retransmit, ack_address)
                                print(f"---Retransmitted frame {requested_frame} to Client {ack_client_id}")
                                self.clients[ack_address].retransmissions+=1
                               
                                with self.clients_lock:
                                    if ack_address in self.clients :
                                        self.clients[ack_address].acknowledged_frame = ack_num
                                        print(f"---Client {ack_client_id}'s last acknowledged frame updated to {ack_num} due to retransmission request")
                                        print('*****\n')

                        acks = [client_info.acknowledged_frame for client_info in self.clients.values()]
                        
                        
                        if time.time() - self.clients[ack_address].last_ack_time > 5:
                            print(f"~~~~~Timeout waiting for ACK for frames {sent_frames} from Client {id_process}")
                            for frame_to_check in sent_frames:
                                if self.clients[address].acknowledged_frame < frame_to_check:  
                                    self.safe_sendto(frame, address)
                                    print(f"~~~~~Resent frame {window_start} to Client {id_process}")
                                    self.clients[address].retransmissions+=1
                                    self.clients[ack_address].last_ack_time = time.time()
                       
                        # Check for a global timeout to avoid infinite waiting
                        if time.time() - timeout_start > 30:
                            print("Timeout waiting for all ACKs. Restarting from start of window...")
                            break      
                except Exception as e:
                            print(e)          

                time.sleep(0.1) 
                

            with self.clients_lock:
                checksum = self.calculate_file_hash(self.file_path)
                eof_frame = f'EOF,{checksum}'
                self.send_sock.sendto(eof_frame.encode(), address)
                print(f"Sent end-of-file signal to Client {id_process}")
            self.active_threads.remove(threading.currentThread())

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
                        
                        print("All client requests received. Starting to handle requests.\n")
                        print("================================ [ BEGIN ] ================================ ✨\n")
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