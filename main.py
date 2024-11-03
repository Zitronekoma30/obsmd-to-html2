import argparse
import obsidian_to_html.md_html as md_html
import os
import hashlib
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
import shutil
from threading import Thread, Event
import signal
import sys
from typing import Dict, Optional
import logging
import configparser
import json
import cgi



# workaround global variables for HTTPRequestHandler
inpt_pth = ""
outpt_pth = ""
config_pth = ""

request_passwd = ""

class GracefulServer:
    def __init__(self, output_path: str, md_path: str, config_path:str, file_ids: Dict, 
                 ip: str = "localhost", port: int = 80):
        self.output_path = output_path
        self.md_path = md_path
        self.config_path = config_path
        self.file_ids = file_ids
        self.ip = ip
        self.port = port
        self.stop_event = Event()
        self.httpd: Optional[HTTPServer] = None
        self.request_thread: Optional[Thread] = None
        
        # Setup logging with both file and console handlers
        self.setup_logging()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler('server.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(console_handler)

    def signal_handler(self, signum, frame):
        logging.info(f"Received signal {signum}. Shutting down gracefully...")
        self.stop_event.set()
        if self.httpd:
            self.httpd.server_close()
        sys.exit(0)

    def handle_requests(self):
        while not self.stop_event.is_set():
            try:
                self.httpd.handle_request()
            except Exception as e:
                logging.error(f"Error handling request: {e}", exc_info=True)
                # Short sleep to prevent tight loop if there's a persistent error
                time.sleep(0.1)

    def run(self):
        try:
            os.chdir(self.output_path)
        except Exception as e:
            logging.error(f"Failed to change directory to {self.output_path}: {e}", 
                         exc_info=True)
            return

        try:
            self.httpd = HTTPServer((self.ip, self.port), CustomHTTPRequestHandler)
            self.httpd.timeout = 1  # Set timeout for handle_request()
        except Exception as e:
            logging.error(f"Failed to start HTTP server on {self.ip}:{self.port}: {e}", 
                         exc_info=True)
            return

        logging.info(f"Serving HTTP on {self.ip} port {self.port} "
                    f"(http://{self.ip}:{self.port}/) ...")

        self.request_thread = Thread(target=self.handle_requests)
        self.request_thread.daemon = True
        self.request_thread.start()

        last_health_check = time.time()
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # Log health check every 5 minutes
                if current_time - last_health_check >= 300:  # 5 minutes
                    logging.info("Server health check - Running")
                    last_health_check = current_time
                
                # Check for changes in md files
                if check_for_changes(self.md_path, self.file_ids):
                    logging.info("Changes detected, rebuilding html files")
                    self.file_ids = convert_all_md_files(self.output_path, 
                                                       self.md_path, self.config_path)
                
                # Verify request thread is still alive
                if not self.request_thread.is_alive():
                    logging.error("Request handler thread died. Restarting...")
                    self.request_thread = Thread(target=self.handle_requests)
                    self.request_thread.daemon = True
                    self.request_thread.start()
                
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(1)  # Prevent tight loop in case of persistent errors

def check_for_changes(md_path, file_ids):
    new_file_ids = {}
    for root, _, files in os.walk(md_path):
        for file in files:
            if file.endswith(".md"):
                full_path_to_file = md_path + os.sep + file
                new_file_ids[file] = generate_dynamic_id(full_path_to_file)
    for key in file_ids:
        if key not in new_file_ids:
            print(f"File {key} has been deleted, rebuilding html files")
            print(new_file_ids)
            return True
        if file_ids[key] != new_file_ids[key]:
            print(f"File {key} has been modified, rebuilding html files")
            return True
    for key in new_file_ids:
        if key not in file_ids:
            print(f"File {key} has been added, rebuilding html files")
            return True
    return False

class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Check the file extension and set Content-Type accordingly
        print("Path:", self.path)
        if self.path.endswith(".css"):
            self.send_header("Content-Type", "text/css; charset=utf-8")
        elif self.path.endswith(".js"):
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
        else:
            self.send_header("Content-Type", "text/html; charset=utf-8")
        super().end_headers()
    
    def do_GET(self):
        if self.path == f"/rebuild-pages-pw:{request_passwd}":
            convert_all_md_files(outpt_pth, inpt_pth, config_pth)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Pages rebuilt")
        else:
            super().do_GET()  
    
    def do_POST(self):
        if self.path == "/submit-booking":
            ctype, pdict = cgi.parse_header(self.headers.get('Content-Type'))
            if ctype == 'multipart/form-data':
                pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
                pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
                form_data = cgi.parse_multipart(self.rfile, pdict)
                
                name = form_data.get('name')[0]
                email = form_data.get('email')[0]
                dates = form_data.get('dates')[0]
                guests = form_data.get('guests')[0]
                
                # Process the form data as needed
                print(f"Received booking request from {name} ({email}) for dates {dates} with {guests} guests.")
                
                # Send a JSON response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    'status': 'success',
                    'message': 'Booking request received'
                }
                self.wfile.write(bytes(json.dumps(response), 'utf-8'))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid form data")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def serve_output_html(output_path, md_path, file_ids, ip="localhost", port=80, config_path=None):
    server = GracefulServer(output_path, md_path, config_path, file_ids, ip, port)
    server.run()


def generate_dynamic_id(file_path):
    mtime = os.path.getmtime(file_path)
    hash_input = f"{file_path}-{mtime}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

def convert_all_md_files(output_path, input_path, config_path=None):
    print("Converting all md files to html")
    print("Input path:", input_path)
    print("Output path:", output_path)
    # remove all files in output path
    for root, _, files in os.walk(output_path, topdown=False):
        for file in files:
            file_path = os.path.join(output_path, file)
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # Convert all md files to html
    file_dynamic_ids = {}
    pages = []
    for root, _, files in os.walk(input_path):
        for file in files:
            if file.endswith(".md"):
                full_path_to_file = input_path + os.sep + file
                print("Converting", full_path_to_file)
                
                html_file_name, tags = md_html.md_to_html(full_path_to_file, output_path, config_path)

                md_file_creation_time = os.path.getctime(full_path_to_file)
                md_file_creation_date = time.strftime('%d.%m.%Y', time.localtime(md_file_creation_time))
                pages.append({"name": html_file_name, "tags": tags, "date": md_file_creation_date, "time": md_file_creation_time})
                
                file_dynamic_ids[file] = generate_dynamic_id(full_path_to_file)

    # sort pages by most recent date
    pages.sort(key=lambda x: x["time"], reverse=True)

    # generate home page
    md_html.generate_home_page(pages, output_path, config_path)

    # copy icon.png to output path
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    if os.path.exists(icon_path):
        shutil.copy(icon_path, output_path)

    # copy all images to output path
    for root, _, files in os.walk(input_path):
        if root == input_path:  # Only process files in the root directory
            for file in files:
                if file.endswith(".png") or file.endswith(".jpg") or file.endswith(".jpeg"):
                    full_path_to_file = os.path.join(root, file)
                    shutil.copy(full_path_to_file, output_path)

    # copy input_path/pages folder to output_path/pages
    pages_path = os.path.join(output_path, "pages")
    src_pages_path = os.path.join(input_path, "pages")
    if os.path.exists(pages_path):
        shutil.rmtree(pages_path)
    if os.path.exists(src_pages_path):
        shutil.copytree(src_pages_path, pages_path)
        print(f"Copied pages folder from {src_pages_path} to {pages_path}")
    else:
        print(f"Source pages folder {src_pages_path} does not exist")


    # add style files
    md_html.copy_style_files(output_path)

    return file_dynamic_ids

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert markdown file to html and maintain a directory of html files to serve as a website")
    # add arguments for md input file directory and output dir
    parser.add_argument("md", help="Markdown files to convert to html")
    parser.add_argument("output", help="Output directory for html files")
    parser.add_argument("ip", help="IP address to serve the html files on", default="localhost")
    parser.add_argument("port", type=int, help="Port to serve the html files on", default=80)
    # TODO: add optional argument for config file and add pw to config
    parser.add_argument("--config", help="Config file for html conversion and security")
    args = parser.parse_args()
    
    md_path = args.md
    output_path = args.output
    config_path = args.config

    inpt_pth = md_path
    outpt_pth = output_path
    config_pth = config_path

    # load password from security section of config file
    if config_path:
        config = configparser.ConfigParser()
        config.read(config_path)
        request_passwd = config["security"]["password"]
    else:
        request_passwd = "password"

    # convert md files to html
    ids = convert_all_md_files(output_path, md_path, config_path)

    # serve html files
    serve_output_html(output_path, md_path, ids, args.ip, args.port, config_path)
