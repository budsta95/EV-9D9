import EV9D9
import asyncio
import db_updater
import keep_alive
from threading import Thread

def start():
  loop = asyncio.get_event_loop()

  print("Starting db_updater")
  loop.create_task(db_updater.run())
  print("Starting EV9D9")
  loop.create_task(EV9D9.start_discord_client())
  print("Starting keepalive server")
  loop.create_task(keep_alive.keep_alive())

  Thread(target=loop.run_forever())

if __name__ == '__main__':
    start()