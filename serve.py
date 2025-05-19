import os
from flask import Flask, request, abort, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Directory to store uploaded files.  Make sure this directory exists.
UPLOAD_DIR = 'uploads'
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@app.route('/upload', methods=['POST'])
def handle_post():
    """
    Handles HTTP POST requests to the '/upload' URL.
    It saves the uploaded file to the server's filesystem,
    naming the file with the client's IP address.

    Returns:
        tuple: A tuple containing a success message and a 200 OK status code,
               or an error message and a 400 Bad Request status code.
    """
    if 'file' not in request.files:
        abort(400, 'No file provided')

    file = request.files['file']
    if file.filename == '':
        abort(400, 'Empty filename')

    if file:
        # Use the client's IP address as the filename.
        filename = request.remote_addr.replace(":", "_")  # Use _ instead of : which are invalid in filenames
        filename = secure_filename(filename) # Sanitize the filename
        filepath = os.path.join(UPLOAD_DIR, filename)
        try:
            file.save(filepath)
            return f'File uploaded successfully to {filepath}', 200
        except Exception as e:
            print(f"Error saving file: {e}")
            abort(500, f"Error saving file: {e}")  # Handle file save errors
    abort(400, 'Invalid file') #general error

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

    # Sanitize the node_ip parameter in case it comes from user
    filename = secure_filename(node_ip.replace(":", "_"))
    filepath = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(filepath):
        abort(404, 'File not found')

    try:
        # Use send_file to send the file.  This handles many of the details
        # (e.g., setting the Content-Disposition header).
        response = send_file(filepath, as_attachment=True)
        os.remove(filepath)  # Delete the file after sending it.
        return response
    except Exception as e:
        print(f"Error sending/deleting file: {e}")
        abort(500, f"Error sending/deleting file: {e}")

if __name__ == '__main__':
    # Start the Flask development server.
    # The debug=True option allows the server to restart automatically
    # when you make changes to the code.  This is useful for development.
    app.run(host='0.0.0.0', port=8080, debug=True)
    # 0.0.0.0 makes the server accessible from outside the local machine
    # Port 8080 is a common port for web applications.
