from flask import Flask, render_template
import threading
import time
import websocket

app = Flask(__name__)

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
    threading.Thread(target=run).start()

def start_websocket_client():
    ws = websocket.WebSocketApp("ws://localhost:8765",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Start the WebSocket client in a separate thread
    threading.Thread(target=start_websocket_client).start()
    app.run(debug=True, use_reloader=False)  # use_reloader=False to prevent the thread from starting twice
