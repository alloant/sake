#!/usr/bin/env python

from flask import current_app
import asyncio
import websockets
#from websockets.sync.client import connect
import json

async def send_message(message):
    #async with websockets.connect(f"wss://{current_app.config['SOCK_SERVER']}:8765/") as websocket:
    async with websockets.connect(f"ws://localhost:8765/") as websocket:
        try:
            await websocket.send(json.dumps(message))
        except:
            pass
