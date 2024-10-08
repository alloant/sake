#!/usr/bin/env python

from flask import current_app
import asyncio
#import websockets
#import websocket
#from websockets.sync.client import connect
import json

async def send_message(message):
    #async with websockets.connect(f"wss://{current_app.config['SOCK_SERVER']}:8765/") as websocket:
    async with websockets.connect(f"ws://localhost:8765/") as websocket:
        try:
            await websocket.send(json.dumps(message))
        except:
            pass


def on_message(ws, message):
    print(f"Received from server: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws):
    print("Connection closed")

def on_open(ws):
    def run():
        while True:
            time.sleep(5)  # Wait for 5 seconds before sending a message
            message = "Hello from Flask client!"
            ws.send(message)
            print(f"Sent to server: {message}")

def start_websocket_client():
    ws = websocket.WebSocketApp("ws://localhost:8765",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()
