from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def main():
    return "Your bot is alive!"

def run():
    print("Running keepalive server")
    app.run(host="0.0.0.0", port=8235)

async def keep_alive():
    print("Initializing keepalive server")
    server = Thread(target=run)
    server.start()

