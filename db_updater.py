from dotenv import load_dotenv
import os
import datetime
import asyncio
import alpaca_trade_api as alpaca
import time
from replit import db
#set up python env (used to access server environment variables)
load_dotenv()

#grab the accounts table
accounts = db.get('Accounts')
if accounts == None:
  print("Accounts table does not exist, creating...")
  accounts = {}
  db['Accounts'] = accounts

db_prices = db.get('Prices')
if db_prices == None:
  print("Prices table does not exist, creating...")
  db_prices = {}
  db['Prices'] = db_prices

all_accounts = {}

api = alpaca.REST(os.getenv('API_KEY'), os.getenv('SECRET_KEY'), os.getenv('ENDPOINT_URL'))
clock = api.get_clock()
print(clock)
assets = api.list_assets()
prices = {}
for a in assets:
    if a.symbol == 'SPY':
        print(a.exchange)
    if a.tradable and a.status == 'active' and (a.exchange == 'NYSE' or a.exchange == 'NASDAQ' or a.exchange == 'ARCA'):
        prices[a.symbol] = 0.00

print("Done importing assets")
bars = {}

def read_prices_to_db():
    global db_prices
    db['Prices'] = db_prices

def read_accounts_to_db():
    global accounts
    db['Accounts'] = accounts
    

async def update_prices():
    print("Updating Prices...")
    global prices,db_prices
    symbols = set()
    counter = 0
    for a in prices:
        counter += 1
        symbols.add(a)
        if counter == 199:
            bars = api.get_barset(symbols=symbols, timeframe='minute', limit=1)
            for b in bars:
                if bars[b]:
                    prices[b] = bars[b][0].c
            symbols = set()
            counter = 0
        if counter % 8000 == 0:
            await asyncio.sleep(3)
    bars = api.get_barset(symbols=symbols, timeframe='minute', limit=1)
    for b in bars:
        if bars[b]:
            prices[b] = bars[b][0].c

    db_prices = prices
    print("\tFinished!")



def get_total_value(account):
    global prices
    total_balance = float(account['balance'])
    for p in account['positions']:
        total_balance += float( prices[p] * account['positions'][p]['amount'] )
    print("Total Balance = " + str(total_balance))
    return total_balance

def update_account_history_min(first):
    print("Updating Accounts...")
    global all_accounts, accounts
    all_accounts = db.get('Accounts')
    for a in all_accounts.keys():
        day_of_week = datetime.datetime.today().weekday()
        now = datetime.datetime.now()
        my_val = get_total_value(all_accounts[a])
        weekday_str = str(day_of_week) + '/' + str(now.hour) + '/' + str(now.minute)
        all_accounts[a]['history']['weekday'][weekday_str] = my_val
        if first:
            everyday_str = str(now.year) + '/' + str(now.month) + '/' + str(now.day)
            all_accounts[a]['history']['everyday'][everyday_str] = my_val
        
        print('\tUpdated Account: ' + str(a))
    accounts = all_accounts
    read_accounts_to_db()
    print("\tFinished!")
            

async def run():
    first = True
    while True:#clock.is_open:
      if clock.is_open:
        print('collecting!')
        now = datetime.datetime.now()
        next_1_min = (now.minute)%60
        next_5_min = (now.minute+5)%60
        next_hour = now.hour
        if next_5_min < now.minute:
            next_hour += 1
        done = False
        while(datetime.datetime.now().minute != next_5_min or datetime.datetime.now().hour != next_hour):
            if datetime.datetime.now().minute >= next_1_min%60: 
                print(str(datetime.datetime.now().hour) + ':' + str(datetime.datetime.now().minute))
                await update_prices()
                if not done:
                    update_account_history_min(first)
                    done = True
                    
                read_prices_to_db()
                next_1_min = datetime.datetime.now().minute + 1
                if first:
                    first = False
            print("sleeping")
            await asyncio.sleep(10)

        print("sleeping2")
        await asyncio.sleep(10)
      else:
        print("Market is closed")
        await update_prices()
        update_account_history_min(False)    
        read_prices_to_db()
        first = True
        await asyncio.sleep(1800)


async def run2():
  while True:
    if True:#clock.is_open:
        print("clock is open")
        await collect()
    else:
        print("clock is closed")
    await asyncio.sleep(1)