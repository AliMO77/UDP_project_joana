# GO-BACK-N UDP File Transfer System

## Overview
This project is a UDP-based file transfer system designed to transfer files from a server to multiple clients concurrently. It includes integrity checks using SHA-256 hashing to ensure file consistency. The system uses a sliding window protocol to manage network traffic and handle out-of-order and lost frames.

## Features
- **UDP Protocol**: Utilizes the User Datagram Protocol for fast, connectionless transmission.
- **Concurrent Clients**: Supports multiple clients receiving files simultaneously.
- **File Integrity**: Implements SHA-256 hashing to verify the integrity of received files.
- **Sliding Window Protocol**: Manages frames using a sliding window to ensure efficient and reliable transmission.
- **Retransmission**: Handles lost or out-of-order frames by requesting retransmissions from the server.

## Prerequisites
- Python 3.x
- Access to a UNIX-like terminal (Linux, macOS, or WSL on Windows).

## Setup
1. Clone the repository:
   ```sh
   git clone https://your-repository-url
   cd your-repository-directory

## Running the Server
1. To start the server, navigate to the directory containing `FileServer.py` and run:
   ```sh
    python3 FileServer.py


This will start the file server, ready to accept connections from clients.

Running the Client(s):

2. To start a client session, use the following command:

    ```sh

    python3 client_initiator.py <num_processes> <filename>

    <id_process>: Automatically assigned when client is instantiated, no need to specify it.
    <num_processes>: Total number of client processes to simulate.
    <filename>: The name of the file to transfer.
     
    <probability:>: randomly assigned client is instantiated, no need to specify it.
    <protocol>: GBN only.no need to specify it.
    <probability:>: randomly assigned when client is instantiated, no need to specify it.

    

3. Example:

    ```sh

    python3 client_initiator.py 5 myfile.txt

## How It Works

    Server: Waits for file requests and sends the requested file in frames, handling retransmission requests as needed.
    Client: Requests a file and receives it in frames, verifying the file integrity at the end of the transmission using a SHA-256 hash received from the server.

Customization

You can customize various parameters within the FileClient and FileServer classes, including:
    Window size
    Timeout durations
    And more


**Notes for Further Development:**
- **Comments and Documentation**: Ensure your code is well-commented and documented. This helps others understand and contribute to your project.
- **Error Handling**: Robust error handling makes your application more reliable and easier to debug.
- **Testing**: Implement comprehensive testing to ensure your system works as expected under various network conditions and loads.
- **Security**: Consider the security implications of your system, especially if it's used in a production environment.

