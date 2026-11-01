#!/usr/bin/env python3
"""Minimal serial-over-HTTP bridge for the A7M3 QEMU console.

QEMU exposes the guest UART on a TCP chardev; this script connects to it and
serves a small web terminal so the shell is usable from any browser.
"""
import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MAXBUF = 400000

buf = bytearray()
lock = threading.Lock()
conn = None
connected = False
serial_addr = ("127.0.0.1", 4444)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>A7M3 QEMU shell</title>
<style>
body{background:#111;color:#ddd;font-family:Consolas,monospace;margin:0}
#bar{background:#222;padding:8px;font-size:13px}
#out{white-space:pre-wrap;padding:10px;font-size:13px;line-height:1.25;
     height:calc(100vh - 90px);overflow:auto;background:#000}
#in{width:calc(100% - 90px);background:#000;color:#0f0;border:1px solid #444;
    padding:6px;font-family:Consolas,monospace;font-size:13px}
button{background:#333;color:#eee;border:1px solid #555;padding:6px 14px}
</style></head><body>
<div id="bar">A7M3 QEMU 串口终端（root shell）<span id="st"> · connecting…</span></div>
<div id="out"></div>
<div style="padding:6px"><input id="in" placeholder="输入命令后回车（例如 ls /）" autofocus>
<button onclick="send()">发送</button></div>
<script>
let since=0;
async function poll(){
  try{
    const r=await fetch('/out?since='+since); const j=await r.json();
    if(j.text){const o=document.getElementById('out');o.textContent+=j.text;
      o.scrollTop=o.scrollHeight;}
    since=j.since; document.getElementById('st').textContent=' · '+j.state;
  }catch(e){document.getElementById('st').textContent=' · disconnected';}
  setTimeout(poll,400);
}
async function send(){
  const i=document.getElementById('in'); const v=i.value; i.value='';
  await fetch('/send',{method:'POST',body:v});
}
document.getElementById('in').addEventListener('keydown',e=>{
  if(e.key==='Enter'){e.preventDefault();send();}
});
poll();
</script></body></html>"""


def reader():
    global conn, connected
    while True:
        try:
            s = socket.create_connection(serial_addr, timeout=2)
            s.settimeout(1)
            conn = s
            connected = True
            while True:
                try:
                    data = s.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                with lock:
                    buf.extend(data)
                    if len(buf) > MAXBUF:
                        del buf[: len(buf) - MAXBUF]
        except Exception:
            pass
        connected = False
        conn = None
        time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/out"):
            q = parse_qs(urlparse(self.path).query)
            try:
                since = int(q.get("since", ["0"])[0])
            except ValueError:
                since = 0
            with lock:
                total = len(buf)
                if since < 0 or since > total:
                    since = 0
                data = bytes(buf[since:])
            text = data.decode("utf-8", "replace")
            body = json.dumps({
                "since": total,
                "text": text,
                "state": "connected" if connected else "waiting for QEMU serial",
            })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGE.encode())

    def do_POST(self):
        if self.path == "/send":
            n = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(n).decode("utf-8", "replace")
            ok = False
            if conn is not None:
                try:
                    conn.sendall(data.encode() + b"\r")
                    ok = True
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": ok}).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    global serial_addr
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--serial-host", default="127.0.0.1")
    ap.add_argument("--serial-port", type=int, default=4444)
    args = ap.parse_args()

    serial_addr = (args.serial_host, args.serial_port)
    threading.Thread(target=reader, daemon=True).start()

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print("serving http://127.0.0.1:%d/ (serial %s:%d)"
          % (args.port, args.serial_host, args.serial_port), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
