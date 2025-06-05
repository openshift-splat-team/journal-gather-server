from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os # Import the os module for path manipulation
from socketserver import ThreadingMixIn # Import ThreadingMixIn for multithreading
import logging # Import the logging module
import datetime
import time

PORT = 8000
LOG_DIR = "/logs" # Directory to store the log files

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Also log to console
    ]
)

def delete_stale_logs(days_old=1, dry_run=False, directory_path=LOG_DIR):
    """
    Scans a directory and (optionally) deletes files created more than a specified number of days ago.

    Args:
        days_old (int): The number of days (inclusive) a file must be older than to be deleted.
                        Default is 1 day.
        dry_run (bool): If True, the script will only report which files would be deleted
                        without actually deleting them. Default is False.
        directory_path (str): The path to the directory to scan.
    """
    # Check if the directory exists
    if not os.path.isdir(directory_path):
        logging.critical(f"Error: Directory '{directory_path}' does not exist.")
        return

    # Calculate the cutoff time (current time minus specified days)
    # Using modification time as it's more reliable across OS for "oldness"
    cutoff_timestamp = time.time() - (days_old * 24 * 60 * 60)
    
    logging.info(f"Scanning directory: {directory_path}")
    action_verb = "Would delete" if dry_run else "Deleting"
    logging.info(f"{action_verb} files older than {days_old} day(s) (based on modification time)...")
    if dry_run:
        logging.info("--- DRY RUN MODE: No files will actually be deleted. ---")

    deleted_count = 0
    skipped_count = 0

    try:
        # Walk through all files and subdirectories
        for root, _, files in os.walk(directory_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                try:
                    # Get the modification time of the file
                    # os.path.getmtime returns the time in seconds since the epoch
                    file_mod_time = os.path.getmtime(file_path)

                    if file_mod_time < cutoff_timestamp:
                        # File is older than the cutoff
                        if dry_run:
                            logging.info(f"  Would delete: {file_path}")
                            deleted_count += 1 # Count as 'would be deleted'
                        else:
                            os.remove(file_path)
                            logging.info(f"  Deleted: {file_path}")
                            deleted_count += 1
                    else:
                        # File is not old enough to be deleted
                        logging.debug(f"  Skipped (too new): {file_path}") 
                        skipped_count += 1

                except OSError as e:
                    logging.critical(f"  Error processing file {file_path}: {e}")
                except Exception as e:
                    logging.critical(f"  An unexpected error occurred with file {file_path}: {e}")

    except Exception as e:
        logging.critical(f"An error occurred during directory scan: {e}")

    logging.info("\n--- Summary ---")
    if dry_run:
        logging.info(f"Total files that WOULD be deleted: {deleted_count}")
    else:
        logging.info(f"Total files deleted: {deleted_count}")
    logging.info(f"Total files skipped (too new or errors): {skipped_count}")
    logging.info("Scan complete.")

# Define a Threading HTTP Server to handle concurrent requests
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    pass

class SimplePOSTHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Ensure the log directory exists
        os.makedirs(LOG_DIR, exist_ok=True)

        # Get the 'node-id' header
        node_ip = self.headers.get('node-id')
        
        # Determine the filename
        if node_ip:
            # Replace any characters that might be invalid in a filename (e.g., colons in IPv6, though we expect IPv4)
            # For IPv4, this is usually fine, but good practice for robustness.
            clean_node_ip = node_ip.replace(':', '_').replace('.', '_') # Simple cleaning, adjust if needed
            filename = f"{clean_node_ip}.txt"
            log_message_prefix = f"node-id '{node_ip}'"
        else:
            filename = "unknown_node.txt"
            log_message_prefix = "No 'node-id' header provided"
            logging.warning("'node-id' header not found. Logging to 'unknown_node.txt'.")

        file_path = os.path.join(LOG_DIR, filename)

        content_length = int(self.headers['Content-Length'])
        post_body_bytes = self.rfile.read(content_length)
        
        # Decode the body for printing and writing
        try:
            post_body_str = post_body_bytes.decode('utf-8')
            # Attempt to pretty-print JSON for console output if applicable
            if 'application/json' in self.headers.get('Content-Type', ''):
                try:
                    console_output = json.dumps(json.loads(post_body_str), indent=2)
                except json.JSONDecodeError:
                    console_output = post_body_str # Fallback if JSON decoding fails
            else:
                console_output = post_body_str
        except UnicodeDecodeError:
            console_output = f"[Undecodable binary data, {len(post_body_bytes)} bytes]"
            post_body_str = console_output # Use this for file writing too if it's truly undecodable

        logging.debug(f"Received POST request body ({len(post_body_bytes)} bytes):")
        logging.debug(console_output)

        # Write the body to the file
        try:
            # Open in append mode ('a') and ensure UTF-8 encoding
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(post_body_str)
                f.write("\n") # Add a couple of newlines to separate entries
            logging.debug(f"Successfully appended body to '{file_path}'")
            response_message = f"POST request received. Body appended to '{filename}'. {log_message_prefix}."
            status_code = 200
        except IOError as e:
            logging.warning(f"ERROR: Could not write to file '{file_path}': {e}")
            response_message = f"Error writing body to file: {e}"
            status_code = 500 # Internal Server Error
        except Exception as e:
            logging.warning(f"An unexpected error occurred: {e}")
            response_message = f"An unexpected server error occurred: {e}"
            status_code = 500

        # Send response back to the client
        self.send_response(status_code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(response_message.encode('utf-8'))

    def do_GET(self):
        # Get the 'node-id' header
        node_ip = self.headers.get('node-id')

        if not node_ip:
            # If node-id header is missing, return 400 Bad Request
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Error: 'node-id' header is required for GET requests.\n")
            logging.warning("GET request failed: 'node-id' header missing.")
            return

        # Determine the filename based on node-id
        clean_node_ip = node_ip.replace(':', '_').replace('.', '_')
        filename = f"{clean_node_ip}.txt"
        file_path = os.path.join(LOG_DIR, filename)

        try:
            # Check if the file exists
            if not os.path.exists(file_path):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error: Log file for node-id '{node_ip}' not found.\n".encode('utf-8'))
                logging.warning(f"GET request failed: File '{file_path}' not found.")
                return

            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            # Send 200 OK response with file content
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(file_content.encode('utf-8'))
            logging.info(f"Successfully served content of '{file_path}' for GET request.")

        except IOError as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error reading file '{file_path}': {e}\n".encode('utf-8'))
            logging.warning(f"GET request failed: Error reading file '{file_path}': {e}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.wfile(f"An unexpected server error occurred: {e}\n".encode('utf-8'))            
            self.end_headers()            
            logging.warning(f"An unexpected server error occurred: {e}\n".encode('utf-8'))            

    def do_DELETE(self):
        delete_stale_logs(days_old=1, dry_run=False, directory_path=LOG_DIR)

        # Get the 'node-id' header
        node_ip = self.headers.get('node-id')

        if not node_ip:
            # If node-id header is missing, return 400 Bad Request
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Error: 'node-id' header is required for DELETE requests.\n")
            logging.warning("DELETE request failed: 'node-id' header missing.")
            return

        # Determine the filename based on node-id
        clean_node_ip = node_ip.replace(':', '_').replace('.', '_')
        filename = f"{clean_node_ip}.txt"
        file_path = os.path.join(LOG_DIR, filename)

        try:
            # Check if the file exists before attempting to delete
            if not os.path.exists(file_path):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error: Log file for node-id '{node_ip}' not found. Nothing to delete.\n".encode('utf-8'))
                logging.warning(f"DELETE request failed: File '{file_path}' not found.")
                return

            # Delete the file
            os.remove(file_path)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.logging.warning(f"Successfully deleted log file for node-id '{node_ip}'.\n".encode('utf-8'))
            logging.info(f"Successfully deleted file: '{file_path}'.")

        except OSError as e: # More specific for file system errors
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error deleting file '{file_path}': {e}\n".encode('utf-8'))
            logging.warning(f"DELETE request failed: Error deleting file '{file_path}': {e}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"An unexpected server error occurred: {e}\n".encode('utf-8'))
            logging.warning(f"DELETE request failed: An unexpected error occurred: {e}")

def run_server():
    server_address = ('', PORT)
    httpd = ThreadedHTTPServer(server_address, SimplePOSTHandler)
    logging.info(f"Starting HTTP server on port {PORT}...")
    logging.info(f"Log files will be stored in the '{LOG_DIR}' directory.")
    logging.info("Listening for POST, GET, and DELETE requests...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.critical("\nShutting down the server.")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()
