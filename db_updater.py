from dotenv import load_dotenv
import os
import datetime
import asyncio
import alpaca_trade_api as alpaca
from EV9D9 import send_alert
from replit import db

#set up python env (used to access server environment variables)
load_dotenv()

#grab the accounts table
db_accounts = db.get('Accounts')
if db_accounts == None:
  print("Accounts table does not exist, creating...")
  db_accounts = {}
  db['Accounts'] = db_accounts

db_prices = db.get('Prices')
if db_prices == None:
  print("Prices table does not exist, creating...")
  db_prices = {}
  db['Prices'] = db_prices

#get alpaca api related stuff
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

#update the prices table in the db
def read_prices_to_db():
    global db_prices
    try:
        db['Prices'] = db_prices
    except Exception as e:
        print("Writing Prices to DB Failed: " + str(e))

#update the accounts table in the db
def read_accounts_to_db():
    global db_accounts
    try:
        db['Accounts'] = db_accounts
    except Exception as e:
        print("Writing Accounts to DB Failed: " + str(e))

#checks to see if market is open    
def is_clock_open():
    global clock
    clock = api.get_clock()
    return clock.is_open

#update the prices table in the db
async def update_prices():
    print("Updating Prices...")
    global db_prices
    try: 
        db_prices = db.get('Prices')
    except Exception as e:
        print("Failed to retrieve table 'Prices' from db: + " + str(e))
    symbols = set()
    counter = 0
    sleeper = 0
    for a in db_prices:
        counter += 1
        sleeper += 1
        symbols.add(a)
        if counter == 199:
            try: 
                bars = api.get_barset(symbols=symbols, timeframe='minute', limit=1)
            except Exception as e:
                print("API Failed: " + str(e))
            for b in bars:
                if bars[b]:
                    db_prices[b] = bars[b][0].c
            symbols = set()
            counter = 0
        if sleeper % 1000 == 0:
            print("\tsleeping, sleeper = " + str(sleeper))
            await asyncio.sleep(3)
    try:
        bars = api.get_barset(symbols=symbols, timeframe='minute', limit=1)
    except Exception as e:
        print("API Failed: " + str(e))
    for b in bars:
        if bars[b]:
            db_prices[b] = bars[b][0].c
    read_prices_to_db()
    print("\tFinished!")


#get an account's total value
def get_total_value(account):
    global db_prices
    #total balance is buying power + value of held positions
    total_balance = float(account['balance'])
    for p in account['positions']:
        total_balance += float( db_prices[p] * account['positions'][p]['amount'] )
    print("\t\tTotal Balance = " + str(total_balance))
    return total_balance

#update each account's history data
def update_account_history_min(first, now):
    print("Updating Accounts...")
    global db_accounts
    try:
        db_accounts = db.get('Accounts')
    except Exception as e:
        print("Failed to retrieve table 'Accounts' from db: " + str(e))
    for a in db_accounts.keys():
        print('\tUpdating Account: ' + str(a))
        day_of_week = datetime.datetime.today().weekday()
        my_val = get_total_value(db_accounts[a])
        weekday_str = str(day_of_week) + '/' + str(now.hour) + '/' + str(now.minute)
        db_accounts[a]['history']['weekday'][weekday_str] = my_val
        if first:
            everyday_str = str(now.year) + '/' + str(now.month) + '/' + str(now.day)
            db_accounts[a]['history']['everyday'][everyday_str] = my_val 
    read_accounts_to_db()
    print("\tFinished!")

#check each account's watchlist            
async def check_watchlist():
    print("Checking Watchlist...")
    global db_accounts
    global db_prices
    try:
        db_accounts = db.get('Accounts')
    except Exception as e:
        print("Failed to retrieve table 'Accounts' from db: " + str(e))
    try:
        db_prices = db.get('Prices')
    except Exception as e:
        print("Failed to retrieve table 'Prices' from db: " + str(e))
    for a in db_accounts.keys():
        print("\tChecking Account " + str(a) + "'s Watchlist")
        try:
            watchlist = db_accounts[a]['watch']
            for ticker in watchlist:
                price = db_prices[ticker]
                if watchlist[ticker] < 0.0:
                    if price < (-1*watchlist[ticker]):
                        msg = "<@" + str(a) + ">, your ticker " + ticker + " is now lower than watch value " + str(watchlist[ticker]) + "!"
                        await send_alert(msg)
                    return
                if price > watchlist[ticker]:
                    msg = "<@" + str(a) + ">, your ticker " + ticker + " is now higher than watch value " + str(watchlist[ticker]) + '!'
                    await send_alert(msg)
                    return
        except KeyError as e:
            print("\tFailed to retrieve " + str(e) + " table from account " + str(a))

async def run():
    #initalize flags and vars
    first = True
    five_first = True
    now = datetime.datetime.now()
    next_odd_min = now.minute

    #main run loop
    while True:
      #only run update fucntions while market is open
      if is_clock_open():
        print('Collecting!')
        #get time data
        now = datetime.datetime.now()
        next_1_min = (now.minute)%60
        next_5_min = (now.minute+5)%60
        if (next_odd_min %2 == 0):
            next_odd_min += 1
        next_hour = now.hour
        if next_5_min < now.minute:
            next_hour += 1
        #do this loop every minute except those divisible by 5
        while(datetime.datetime.now().minute%5 != 0):
            now = datetime.datetime.now()
            if now.minute >= next_1_min%60:
                #update prices once every minute
                five_first = True 
                print(str(now.hour) + ':' + str(now.minute))
                await update_prices()
                next_1_min = now.minute + 1
            if now.minute >= next_odd_min:
                #check watchlist every odd minute
                print("minute: " + str(now.minute) + ", next_odd_minute: " + str(next_odd_min))
                await check_watchlist()
                next_odd_min = next_odd_min + 2
                if next_odd_min > 60:
                    next_odd_min = 1
            #sleep so the bot can process other stuff
            print("Sleeping for 10s")
            await asyncio.sleep(10)
        if (five_first):
            #update account history when time is divisible by 5 minutes
            next_odd_min += 2
            now = datetime.datetime.now()
            print(str(now.hour) + ':' + str(now.minute))
            await update_prices()
            #first is true for the first history update of the day
            update_account_history_min(first, now)
            if first:
                first = False
            five_first = False
        #sleep so the bot can process other stuff
        print("Sleeping2 for 10s")
        await asyncio.sleep(10)
      else:
        #when the market is closed, sleep until it opens again, checking every 30 minutes
        print("Market is closed") 
        print("Sleeping for 30m")
        first = True
        await asyncio.sleep(1800)