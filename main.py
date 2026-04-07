from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


HOST = "127.0.0.1"
PORT = 8000


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), SimpleHTTPRequestHandler)
    print(f"Serving Taiwan EV map at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
