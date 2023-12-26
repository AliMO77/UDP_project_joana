import socket
import random
import hashlib
import socket
import os

class FileClient:
    def __init__(self,id_process,total_process,filename,probability, window,server_ip='127.0.0.1', server_port=12345):
        self.server_address = (server_ip, server_port)
        self.id_process = id_process
        self.total_process = total_process
        self.filename = filename
        self.probability = 0
        self.window = window

        # Create a UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   
    def calculate_file_hash(self,filename):
        hash_func = hashlib.sha256()  # You can choose other algorithms like MD5 or SHA-1
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    
    def verify_file(self, actual_hash, expected_hash):
        if actual_hash == expected_hash:
            print("File is intact and uncorrupted.")
        else:
            print("File corruption detected.")

   
    def request_file(self, file_path='received_file.txt'):
        folder_path = './downloads'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        file_path = os.path.join(folder_path, file_path)
        try:
            # Send request to server
            message = f"request_file,id_process={self.id_process},total_process={self.total_process},filename={self.filename},window_size={self.window}"
            self.sock.sendto(message.encode(), self.server_address)
            print(f"Client {self.id_process} sent request to server for file: {self.filename}")


            with open(file_path, "wb") as file:
                expected_frame = 0
                last = -1
                while True:
                    # Set a timeout for receiving
                    self.sock.settimeout(2)  # 5 seconds for example
                    try:
                        # Receive frame from server
                        file_data, _ = self.sock.recvfrom(4096)

                        # Check for end of file signal (empty packet)
                        content = file_data.decode().split(',')
                        
                        if content[0] == 'EOF':
                            print(f"###################")
                            print(f"Client {self.id_process} received end of file signal.")
                            # Close the file to ensure all data is flushed and written
                            file.close()
                            
                            # Confirmation message after successfully receiving the file
                            checksum = self.calculate_file_hash(file_path)
                            actual_hash=content[1]

                            self.verify_file(actual_hash, checksum)
                            print(f"Client {self.id_process} has received and saved the file to {file_path}")
                            
                            break  # Exit the loop as no more data will be sent

                        # Extract sequence number and data
                        seq_str = file_data[:4].decode()  # First 4 bytes are the sequence number
                        seq_number = int(seq_str)  # Convert sequence number back to integer
                        frame_data = file_data[4:]  # The rest is the frame data
                        
                        # Check if it's the expected frame
                        if seq_number == expected_frame:
                            print(f"Client {self.id_process} received expected frame {seq_number}")
                            file.write(frame_data)  # Write data to file
                            expected_frame += 1  # Move to next expected frame
                            last = seq_number
                        else:
                            print(f"Client {self.id_process} received out-of-order frame {seq_number}. Expected: {expected_frame}")
                            retransmit_msg = f"retransmit,{expected_frame},{self.id_process}"
                            self.sock.sendto(retransmit_msg.encode(), self.server_address)
                       
                        ack_message = f"ack,{last},{self.id_process}"
                        self.sock.sendto(ack_message.encode(), self.server_address)
                        print(f"Client {self.id_process} sent ack {seq_number}") 
                    except socket.timeout:
                            print(f"Client {self.id_process} did not receive frame {expected_frame}, requesting retransmission.")
                            retransmit_msg = f"retransmit,{expected_frame},{self.id_process}"
                            self.sock.sendto(retransmit_msg.encode(), self.server_address)

           

        except Exception as e:
            print(f"An error occurred in Client {self.id_process}: {e}")
        finally:
            print(f"Client {self.id_process} closing the socket.")
            print(f"###################")
            self.sock.close()


