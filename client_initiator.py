# client_initiator.py
import argparse
import threading
from threading import Barrier
import sys
from FileClient import FileClient
import random
import socket

clients = []
ids = []

#  Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Define the client behavior in a separate function or class
def start_client(id_process, total_processes, filename,probability,window,barrier):
    
    client = FileClient(id_process,total_processes,filename,probability,window)
    clients.append(client)
    ids.append(id_process)
    print(f"Client {id_process}/{total_processes} is waiting at the barrier.")
    barrier.wait()
    print(f"Client {id_process}/{total_processes} joined the session.")
   

def request_file(total_processes):
    request_threads = []
    for i in range(total_processes):
        unique_file_path = f"received_file_{i+1}.txt"
        
        # Create a new thread for each client's request
        thread = threading.Thread(target=clients[i].request_file, args=(unique_file_path,))
        request_threads.append(thread)
        thread.start()  # Start the thread

    # Wait for all threads to complete
    for thread in request_threads:
        thread.join()

    print('All clients requests have Completed.')
    eof_frame = b'EOR'
    sock.sendto(eof_frame, ('127.0.0.1', 12345))
    print(f"Sent end-of-requests signal to server")



def start_clients_concurrently(total_processes, filename):
    threads = []
    for i in range(1, total_processes + 1):
        probability = round(random.random(),1)
        window=random.randint(1, 10)
        # Create a new thread for each client
        thread = threading.Thread(target=start_client, args=(i, total_processes, filename,probability,window,barrier))
        threads.append(thread)
        thread.start()  # Start the thread
    
    for thread in threads:
        thread.join()
   
    


# Set up argument parsing
parser = argparse.ArgumentParser(description='Tool to initiate client processes.')
# parser.add_argument('id_process', type=int, help='The number of the current process (e.g., 2)')
parser.add_argument('num_processes', type=int, help='Total number of processes in the communication (e.g., 10)')
parser.add_argument('filename', type=str, help='Name of the file to be sent to each client')
# parser.add_argument('loss_probability', type=float, help='Probability of simulated loss (e.g., 0.1 for 10%)')

# Parse the arguments
args = parser.parse_args()
barrier = Barrier(args.num_processes)
print(f"Initializing Session")
start_clients_concurrently(args.num_processes, args.filename)
print('*********************All clents have joined, Session can start...********************************\n\n')

# Request files once all clients are initialized
request_file(args.num_processes)

