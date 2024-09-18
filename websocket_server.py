#!/usr/bin/env python

import asyncio
import websockets
import ssl
import os

clients = {}

async def handler(ws):
    print('path',ws.path)
    if ws.path != '/':
        clients[ws.path[1:]] = ws
    
    while True:
        try:
            message = await ws.recv()
            message = eval(message)
            
            for i,user in enumerate(message['users']):
                await clients[user].send(f'<div id="sock_id"><span hx-get="/load_socket?msg={message["message"][i]}" hx-trigger="load" hx-swap="outerHTML"></span></div>')
        except:
            print('closed')
            break

#ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
PATH_PEM = os.environ.get('PATH_PEM') \
    or '/cert'

#localhost_pem = f"{PATH_PEM}/server.crt"
#localhost_key = f"{PATH_PEM}/server.key"

#ssl_context.load_cert_chain(localhost_pem, keyfile=localhost_key)

async def main():
    SOCK_SERVER = os.environ.get('SOCK_SERVER')
    print(f'Staring websocket server {SOCK_SERVER}')
    SOCK_SERVER = ""
    #async with websockets.serve(handler, f"{SOCK_SERVER}", 8765, ssl=ssl_context):
    async with websockets.serve(handler, f"{SOCK_SERVER}", 8765):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())



