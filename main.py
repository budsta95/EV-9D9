import EV9D9
import asyncio
import db_updater
from threading import Thread

def start():
  loop = asyncio.get_event_loop()

  print("Starting db_updater")
  loop.create_task(db_updater.run())
  print("Starting paperboy")
  loop.create_task(EV9D9.start_discord_client())
  Thread(target=loop.run_forever())

if __name__ == '__main__':
    start()