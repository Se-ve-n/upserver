import os
import ssl
import argparse
import socketserver
import subprocess
import tempfile
from http.server import SimpleHTTPRequestHandler
from urllib.parse import unquote, quote
from datetime import datetime
import mimetypes

# -------------------------------
# Argument Parser
# -------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="UPSERVER File Server")
    parser.add_argument('--port', type=int, default=7070, help='Port to run the server on (default: 7070)')
    parser.add_argument('--bind', default='0.0.0.0', help='Bind address (default: 0.0.0.0)')
    parser.add_argument('--dir', default='.', help='Directory to serve (default: current directory)')
    parser.add_argument('--ssl', action='store_true', help='Enable HTTPS with SSL certificate')
    parser.add_argument('--cert', help='Path to SSL certificate')
    parser.add_argument('--key', help='Path to SSL private key')
    parser.add_argument('--upload-password', help='Password required to upload files')
    return parser.parse_args()

# -------------------------------
# Self-Signed Cert Generator
# -------------------------------
def generate_self_signed_cert():
    temp_dir = tempfile.gettempdir()
    cert_path = os.path.join(temp_dir, "upserver_cert.pem")
    key_path = os.path.join(temp_dir, "upserver_key.pem")

    if args.ssl:
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            print("🔧 Generating self-signed certificate...")
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", key_path,
                "-out", cert_path,
                "-days", "365",
                "-nodes",
                "-subj", "/CN=UPSERVER"
            ], check=True)

    return cert_path, key_path

# -------------------------------
# Custom Handler
# -------------------------------
class UPSERVERHandler(SimpleHTTPRequestHandler):
    upload_password = ""
    previewable_types = [
        'text/', 'image/', 'application/pdf', 'video/', 'audio/',
        'application/json', 'application/xml', 'application/javascript',
        'text/css', 'text/csv', 'application/x-yaml', 'text/markdown',
    ]

    def do_GET(self):
        if self.path.startswith("/upload"):
            self.handle_upload_page()
        elif self.path.startswith("/preview/"):
            self.handle_file_preview()
        else:
            # Check if this is a file request (not directory)
            path = self.translate_path(self.path)
            if os.path.isfile(path):
                # Check if file is previewable
                mime_type = mimetypes.guess_type(path)[0]
                if mime_type and any(mime_type.startswith(t) for t in self.previewable_types):
                    self.redirect_to_preview(path)
                else:
                    super().do_GET()
            else:
                super().do_GET()

    def redirect_to_preview(self, path):
        relative_path = os.path.relpath(path, os.getcwd())
        encoded_path = quote(relative_path)
        self.send_response(302)
        self.send_header('Location', f'/preview/{encoded_path}')
        self.end_headers()

    def handle_file_preview(self):
        try:
            # Extract the file path from the URL
            relative_path = unquote(self.path[len('/preview/'):])
            full_path = os.path.join(os.getcwd(), relative_path)
            
            if not os.path.isfile(full_path):
                self.send_error(404, "File not found")
                return

            mime_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
            file_size = os.path.getsize(full_path)
            modified_time = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')

            # Generate the preview page
            with open(full_path, 'rb') as f:
                content = f.read()

            # ASCII Art Logo
            logo = r"""
  _    _ _____ _____ _____ _____ _____ _____ _____ 
 | |  | |  _  /  ___|  ___/  ___|_   _|  _  |  ___|
 | |  | | | | \ `--.| |__ \ `--.  | | | | | | |__  
 | |/\| | | | |`--. \  __| `--. \ | | | | | |  __| 
 \  /\  \ \_/ /\__/ / |___/\__/ /_| |_\ \_/ / |___ 
  \/  \/ \___/\____/\____/\____/ \___/ \___/\____/  
            """

            # Different preview sections based on file type
            preview_content = ""
            if mime_type.startswith('image/'):
                preview_content = f'<div class="preview-area"><img src="/{relative_path}" alt="Image preview" style="max-width: 100%; max-height: 70vh;"></div>'
            elif mime_type.startswith('text/') or mime_type in ['application/json', 'application/xml']:
                try:
                    text_content = content.decode('utf-8')
                    preview_content = f'<div class="preview-area"><pre>{text_content}</pre></div>'
                except UnicodeDecodeError:
                    preview_content = '<div class="preview-area"><p>Binary content cannot be displayed</p></div>'
            elif mime_type == 'application/pdf':
                preview_content = f'<div class="preview-area"><embed src="/{relative_path}" type="application/pdf" width="100%" height="600px"></div>'
            elif mime_type.startswith('video/'):
                preview_content = f'''
                <div class="preview-area">
                    <video controls style="max-width: 100%; max-height: 70vh;">
                        <source src="/{relative_path}" type="{mime_type}">
                        Your browser does not support the video tag.
                    </video>
                </div>
                '''
            elif mime_type.startswith('audio/'):
                preview_content = f'''
                <div class="preview-area">
                    <audio controls style="width: 100%">
                        <source src="/{relative_path}" type="{mime_type}">
                        Your browser does not support the audio element.
                    </audio>
                </div>
                '''
            else:
                preview_content = '<div class="preview-area"><p>Preview not available for this file type</p></div>'

            response = f"""<!DOCTYPE html>
<html>
<head>
    <title>PREVIEW: {relative_path}</title>
    <style>
        @font-face {{
            font-family: 'Cyber';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }}
        
        body {{
            background-color: #000000;
            color: #00ff00;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 0;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 10px;
        }}
        
        .logo {{
            color: #00ff00;
            font-family: monospace;
            white-space: pre;
            margin-right: 30px;
            font-size: 10px;
            line-height: 1.2;
        }}
        
        .file-info {{
            flex-grow: 1;
        }}
        
        h1 {{
            color: #00ff00;
            margin: 0;
            font-size: 24px;
            text-shadow: 0 0 5px #00ff00;
        }}
        
        .path {{
            color: #00ff00;
            font-size: 14px;
            margin-top: 5px;
        }}
        
        .preview-area {{
            margin: 20px 0;
            padding: 15px;
            background-color: #001a00;
            border: 1px solid #003300;
            max-height: 70vh;
            overflow: auto;
        }}
        
        .file-meta {{
            background-color: #001a00;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid #003300;
        }}
        
        .action-btns {{
            margin-top: 20px;
        }}
        
        .btn {{
            display: inline-block;
            background-color: #003300;
            color: #00ff00;
            padding: 8px 15px;
            border: 1px solid #00ff00;
            text-decoration: none;
            margin-right: 10px;
        }}
        
        .btn:hover {{
            background-color: #00ff00;
            color: #000000;
        }}
        
        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">{logo}</div>
            <div class="file-info">
                <h1>FILE PREVIEW: {relative_path}</h1>
                <div class="path">Type: {mime_type} | Size: {self.format_size(file_size)} | Modified: {modified_time}</div>
            </div>
        </div>
        
        <div class="file-meta">
            <strong>File Path:</strong> {relative_path}<br>
            <strong>MIME Type:</strong> {mime_type}<br>
            <strong>Size:</strong> {self.format_size(file_size)}<br>
            <strong>Last Modified:</strong> {modified_time}
        </div>
        
        {preview_content}
        
        <div class="action-btns">
            <a href="/{relative_path}" class="btn" download>DOWNLOAD</a>
            <a href="/" class="btn">BACK TO FILES</a>
        </div>
    </div>
</body>
</html>"""

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error generating preview: {str(e)}")

    def handle_upload_page(self):
        if not self.upload_password:
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Upload functionality is disabled.".encode("utf-8"))
            return

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>UPServer</title>
            <style>
                body { background:black; color:lime; font-family:monospace; padding:2em; }
                input, button { margin-top:1em; }
            </style>
        </head>
        <body>
            <h2>🔐 Upload to UPSERVER</h2>
            <input type="password" id="password" placeholder="Enter password" /><br>
            <input type="file" id="fileInput" /><br>
            <button onclick="upload()">Upload</button>
            <pre id="result"></pre>

            <script>
            async function upload() {
                const file = document.getElementById("fileInput").files[0];
                const password = document.getElementById("password").value;
                const result = document.getElementById("result");

                if (!file) {
                    result.textContent = "❗ No file selected.";
                    return;
                }

                const form = new FormData();
                form.append("file", file);
                form.append("password", password);

                const res = await fetch("/upload", {
                    method: "POST",
                    body: form
                });

                const text = await res.text();
                result.textContent = text;
            }
            </script>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path != "/upload":
            self.send_error(404)
            return
        if not self.upload_password:
            self.send_error(403, "Upload is disabled")
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "Invalid Content-Type")
            return

        boundary = content_type.split("boundary=")[-1].encode()
        remain = int(self.headers.get("Content-Length"))
        data = self.rfile.read(remain)

        parts = data.split(b"--" + boundary)
        uploaded = False
        authorized = False
        file_data = None
        filename = None
        for part in parts:
            if b"Content-Disposition" not in part:
                continue
            if b'name="password"' in part:
                value = part.split(b"\r\n\r\n")[1].strip(b"\r\n--")
                try:
                    submitted_password = value.decode(errors="ignore").strip()
                    if submitted_password and submitted_password == self.upload_password:
                        authorized = True
                except:
                    pass
            elif b'name="file"' in part:
                headers, file_data = part.split(b"\r\n\r\n", 1)
                file_data = file_data.rstrip(b"\r\n--")
                disposition = headers.decode(errors="ignore")
                if 'filename="' in disposition:
                    filename = disposition.split('filename="')[1].split('"')[0]
                if not filename:
                    filename = "upload_" + datetime.now().strftime("%Y%m%d%H%M%S")
        if authorized and file_data and filename:
            with open(filename, "wb") as f:
                f.write(file_data)
            uploaded = True

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if not authorized:
            self.wfile.write("Incorrect password".encode("utf-8"))
        elif uploaded:
            self.wfile.write(f"File uploaded as {filename}".encode())
        else:
            self.wfile.write("No file found".encode("utf-8"))

    def format_size(self, bytes):
        if bytes < 1024:
            return f"{bytes} B"
        elif bytes < 1024 * 1024:
            return f"{bytes/1024:.1f} KB"
        elif bytes < 1024 * 1024 * 1024:
            return f"{bytes/(1024*1024):.1f} MB"
        else:
            return f"{bytes/(1024*1024*1024):.1f} GB"

    def format_date(self, timestamp):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    def get_file_type(self, name):
        if os.path.isdir(name):
            return "DIR"
        mime_type = mimetypes.guess_type(name)[0]
        if not mime_type:
            return "FILE"
        
        if mime_type.startswith('image/'):
            return "IMAGE"
        elif mime_type.startswith('video/'):
            return "VIDEO"
        elif mime_type.startswith('audio/'):
            return "AUDIO"
        elif mime_type.startswith('text/'):
            return "TEXT"
        elif mime_type in ['application/pdf']:
            return "PDF"
        elif mime_type in ['application/json']:
            return "JSON"
        elif mime_type in ['application/xml']:
            return "XML"
        elif mime_type in ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']:
            return "ARCHIVE"
        else:
            return "FILE"

    def list_directory(self, path):
        try:
            file_list = os.listdir(path)
        except OSError:
            self.send_error(404, "Directory not found")
            return None

        file_list.sort(key=lambda a: a.lower())
        displaypath = unquote(self.path)
        total_files = 0
        total_dirs = 0
        total_size = 0

        # Count files and directories
        for name in file_list:
            fullname = os.path.join(path, name)
            if os.path.isdir(fullname):
                total_dirs += 1
            else:
                total_files += 1
                try:
                    total_size += os.path.getsize(fullname)
                except:
                    pass

        # ASCII Art Logo
        logo = r"""

       _ _____   _____ ______ _______      ________ _____  
 | |  | |  __ \ / ____|  ____|  __ \ \    / /  ____|  __ \ 
 | |  | | |__) | (___ | |__  | |__) \ \  / /| |__  | |__) |
 | |  | |  ___/ \___ \|  __| |  _  / \ \/ / |  __| |  _  / 
 | |__| | |     ____) | |____| | \ \  \  /  | |____| | \ \ 
  \____/|_|    |_____/|______|_|  \_\  \/   |______|_|  \_\
        """

        response = f"""<!DOCTYPE html>
<html>
<head>
    <title>UPSERVER File Server</title>
    <style>
        @font-face {{
            font-family: 'Cyber';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }}
        
        body {{
            background-color: #000000;
            color: #00ff00;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 0;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #00ff00;
            padding-bottom: 10px;
        }}
        
        .logo {{
            color: #00ff00;
            font-family: monospace;
            white-space: pre;
            margin-right: 30px;
            font-size: 10px;
            line-height: 1.2;
        }}
        
        .path-info {{
            flex-grow: 1;
        }}
        
        h1 {{
            color: #00ff00;
            margin: 0;
            font-size: 24px;
            text-shadow: 0 0 5px #00ff00;
        }}
        
        .path {{
            color: #00ff00;
            font-size: 14px;
            margin-top: 5px;
        }}
        
        .file-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        
        .file-table th {{
            background-color: #001a00;
            color: #00ff00;
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #00ff00;
        }}
        
        .file-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #003300;
        }}
        
        .file-table tr:hover {{
            background-color: #001a00;
        }}
        
        a {{
            color: #00ff00;
            text-decoration: none;
        }}
        
        a:hover {{
            color: #ffffff;
            text-shadow: 0 0 5px #00ff00;
        }}
        
        .file-icon {{
            margin-right: 5px;
        }}
        
        .footer {{
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #00ff00;
            font-size: 12px;
            color: #009900;
            text-align: center;
        }}
        
        .stats {{
            background-color: #001a00;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid #003300;
        }}
        
        .upload-btn {{
            display: inline-block;
            background-color: #003300;
            color: #00ff00;
            padding: 8px 15px;
            border: 1px solid #00ff00;
            text-decoration: none;
            margin-bottom: 20px;
        }}
        
        .upload-btn:hover {{
            background-color: #00ff00;
            color: #000000;
        }}
        
        .preview-link {{
            color: #00ccff;
            text-decoration: underline;
            margin-left: 10px;
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">{logo}</div>
            <div class="path-info">
                <h1>UPSERVER FILE SYSTEM</h1>
                <div class="path">Path: {os.path.abspath(path)}</div>
            </div>
        </div>
        
        <a href="/upload" class="upload-btn">UPLOAD FILE</a>
        
        <div class="stats">
            Total: {total_files} files, {total_dirs} directories | Total size: {self.format_size(total_size)}
        </div>
        
        <table class="file-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Modified</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>"""

        for name in file_list:
            fullname = os.path.join(path, name)
            is_dir = os.path.isdir(fullname)
            size = 0
            modified = 0
            file_type = self.get_file_type(fullname)
            mime_type = mimetypes.guess_type(fullname)[0]
            
            try:
                stat = os.stat(fullname)
                modified = stat.st_mtime
                if not is_dir:
                    size = stat.st_size
            except:
                pass
                
            icon = ""
            if is_dir:
                icon = "📁"
            elif file_type == "IMAGE":
                icon = "🖼️"
            elif file_type == "VIDEO":
                icon = "🎬"
            elif file_type == "AUDIO":
                icon = "🎵"
            elif file_type == "ARCHIVE":
                icon = "🗄️"
            elif file_type in ["TEXT", "JSON", "XML"]:
                icon = "📝"
            elif file_type == "PDF":
                icon = "📄"
            else:
                icon = "📦"
                
            # Make directories and files clickable
            if is_dir:
                name_display = name + "/"
                link = name + "/"
                actions = ""
            else:
                name_display = name
                link = name
                # Add preview link for viewable files
                if mime_type and any(mime_type.startswith(t) for t in self.previewable_types):
                    actions = f'<a href="/preview/{quote(name)}" class="preview-link">PREVIEW</a>'
                else:
                    actions = ""
                
            response += f"""
                <tr>
                    <td>{icon} <a href="{link}">{name_display}</a></td>
                    <td>{file_type}</td>
                    <td>{self.format_size(size) if not is_dir else '-'}</td>
                    <td>{self.format_date(modified)}</td>
                    <td>{actions}</td>
                </tr>"""

        response += f"""
            </tbody>
        </table>
        
        <div class="footer">
            <div>UPSERVER v1.0 | @seven</div>
            <div>SYSTEM STATUS: ONLINE | SECTOR: {os.path.basename(os.path.abspath(path))}</div>
            <div>LAST REFRESH: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div>/// WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead. ///</div>
        </div>
    </div>
</body>
</html>"""

        encoded = response.encode("utf-8", "surrogateescape")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        return None

# -------------------------------
# Main Entry
# -------------------------------
if __name__ == '__main__':
    args = parse_args()
    os.chdir(args.dir)
    UPSERVERHandler.upload_password = args.upload_password or ""

    with socketserver.TCPServer((args.bind, args.port), UPSERVERHandler) as httpd:
        if args.ssl:
            if not args.cert or not args.key:
                args.cert, args.key = generate_self_signed_cert()

            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=args.cert, keyfile=args.key)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            print(f"UPSERVER serving on {args.bind} port {args.port} (https://{args.bind}:{args.port})")
        else:
            print(f"UPSERVER serving on {args.bind} port {args.port} (http://{args.bind}:{args.port})")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting")
