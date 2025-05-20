import socket
import os
from flask import Flask, request, abort, send_file, jsonify
import threading

UPLOAD_DIR = '/tmp/logs'
app = Flask(__name__)

def handle_client(client_socket, client_address):
    """Handles the connection with a single client and appends to the file."""
    try:
        client_ip = client_address[0]
        filename = f"{client_ip}.txt"
        file_path = os.path.join(UPLOAD_DIR, filename)
        print(f"Connection from {client_address}. Appending data to {file_path}")

        with open(file_path, 'ab') as file:  # Open in append binary mode ('ab')
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break  # Client disconnected
                file.write(data)
        print(f"Data received from {client_address} and appended to {file_path}")
    except Exception as e:
        print(f"Error handling client {client_address}: {e}")
    finally:
        client_socket.close()
        print(f"Connection with {client_address} closed.")

@app.route('/retrieve', methods=['GET'])
def retrieve_file():
    """
    Handles HTTP GET requests to the '/retrieve' URL.
    It retrieves the file associated with the provided 'node-ip' parameter,
    sends the file to the client, and deletes the file from the server.

    Returns:
        Response: The file to be downloaded, or a 404 Not Found error if the
                  file does not exist.
    """
    node_ip = request.args.get('node-ip')
    if not node_ip:
        abort(400, 'Missing node-ip parameter')

    file_name = node_ip + ".txt"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    if not os.path.exists(file_path):
        abort(404, 'File not found')

    try:        
        response = send_file(file_path, as_attachment=True)
        print(f"Retrieved log data for {node_ip}") 

        os.remove(file_path)  # Delete the file after sending it.
        return response
    except Exception as e:
        print(f"Error sending/deleting file: {e}")
        abort(500, f"Error sending/deleting file: {e}")

def run_server():
    app.run(host='0.0.0.0', port=8080, debug=False)

def main():
    """Sets up the TCP server and listens for connections."""
    host = '0.0.0.0'  # Listen on all available interfaces
    port = 12345      # You can choose a different port

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5)  # Allow up to 5 pending connections
        print(f"Listening on {host}:{port}...")

        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            client_thread.start()

    except KeyboardInterrupt:
        print("Server shutting down...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":    
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    print("Flask server started in a new thread.")
    main()