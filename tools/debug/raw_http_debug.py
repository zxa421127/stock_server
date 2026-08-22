# -*- coding: utf-8 -*-
"""Tiny raw TCP listener for distinguishing HTTP requests from TLS handshakes."""
from __future__ import annotations

import argparse
import socket
from datetime import datetime


def safe_decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(20)
        print(f"RAW HTTP DEBUG listening on {args.host}:{args.port}; Ctrl+C 停止")

        while True:
            conn, addr = server.accept()
            with conn:
                try:
                    data = conn.recv(8192)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n[{now}] FROM {addr}; bytes={len(data)}")
                    print("HEX:", data[:64].hex(" "))
                    if data.startswith(b"\x16\x03"):
                        print("TLS/HTTPS 握手，不是普通 HTTP。")
                    elif data.startswith((b"GET ", b"POST ", b"HEAD ", b"PUT ", b"DELETE ")):
                        print("普通 HTTP 请求。")
                    else:
                        print("未知或异常请求。")
                    print(safe_decode(data))

                    body = b"raw debug ok"
                    response = (
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/plain; charset=utf-8\r\n"
                        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                        b"Connection: close\r\n\r\n" + body
                    )
                    conn.sendall(response)
                except Exception as exc:
                    print("处理异常:", repr(exc))


if __name__ == "__main__":
    main()
