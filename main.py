import paperboy
import asyncio
import db_updater
from threading import Thread

def start():
  loop = asyncio.get_event_loop()

  print("Starting db_updater")
  loop.create_task(db_updater.run())
  print("Starting paperboy")
  loop.create_task(paperboy.start_discord_client())
  Thread(target=loop.run_forever())

#print("Starting db_updater")
#Thread(target = db_updater.run).start()
#print("Starting paperboy")
#Thread(target = paperboy.start_discord_client).start()
if __name__ == '__main__':
    start()