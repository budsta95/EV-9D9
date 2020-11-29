import os,re
import discord
from dotenv import load_dotenv
import alpaca_trade_api as alpaca
from datetime import datetime
#import time
#import csv
#import json
import requests
import matplotlib.pyplot as plt
from replit import db

#set up python env (used to access server environment variables)
load_dotenv()



#grab the accounts table
accounts = db.get('Accounts')
if accounts == None:
  print("Accounts table does not exist, creating...")
  accounts = {}
  db['Accounts'] = accounts

#grab the prices table
db_prices = db.get('Prices')
if db_prices == None:
  print("Prices table does not exist, creating...")
  db_prices = {}
  db['Prices'] = db_prices


#set up regex to recognize discord chat commands
sell_order_regex = re.compile('^\!sell (.*) (.*)')
buy_order_regex = re.compile('^\!buy (.*) (.*)')
price_regex = re.compile('^\!price (.*)')
watch_regex = re.compile('^\!watch (.*) (.*)')
week_format_regex = re.compile('^(.*)\/(.*)\/(.*)')

#grab discord tokens from env
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER = os.getenv('DISCORD_SERVER')

#initialize discord client
client = discord.Client()

#initialize alpaca api
api = alpaca.REST(os.getenv('API_KEY'), os.getenv('SECRET_KEY'), os.getenv('ENDPOINT_URL'))
clock = api.get_clock()

#create ticker-name -> company name dict
my_ticker_names = {}
my_data = requests.get('https://api.iextrading.com/1.0/ref-data/symbols').json()
for x in my_data:
    my_ticker_names[x['symbol']] = x['name']

def process_date(my_date):
    cur_day = datetime.today().weekday()
    my_day = int(week_format_regex.match(my_date).group(1))
    return (my_day + (6 - cur_day))%6

def get_prices():
    global db_prices
    db_prices = db.get('Prices')
    return db_prices

#gets the account corresponding to a given player id
def get_account_info(player):
    global accounts
    accounts = db.get('Accounts')
    try:
      target_account = accounts[str(player)]
      #if the player doesn't have an account in the database, create one for them
    except KeyError as e:
      print("Player ID " + str(e) + " not in DB, creating entry")
      my_json = {'player_id': player, 'balance': 1000000, 'positions': {}, 'watch': {}, 'history': {'weekday': {}, 'everyday': {}}}
      accounts[player] = my_json
      db['Accounts'] = accounts
      return my_json
    return target_account

def write_account_info():
    global accounts
    db['Accounts'] = accounts

#check to see if market is open
def is_clock_open():
    global clock
    clock = api.get_clock()
    return clock.is_open

#send a message to the specified discord channel
async def send_alert(message):
    global client
    channelID = 766738096703799306
    channel = client.get_channel(channelID)
    await channel.send(message)

#run the price command
async def price_command(message):
    #match to price command regex
    msg = price_regex.match(str(message.content))
    if msg != None:
        #grab the ticker and coerce it to all upppercase
        ticker = msg.group(1).upper()
        price_day = 0.0
        try:
            if is_clock_open():
                price_day = api.get_barset(ticker, 'day', limit=1)[ticker][0].c
            else:
                price_day = api.get_barset(ticker, 'day', limit=2)[ticker][0].c
                price = get_prices()[ticker]
        except IndexError:
            await message.channel.send('Invalid ticker! Could not retrieve info for ' + ticker)
            return
        diff = float(price) - float(price_day)
        perc_change = ((float(price) / float(price_day)) - 1.00) * 100.0
        my_perc_str = ''
        my_price_str = ''
        my_color = 0xFF0000
        if diff > 0.0:
            my_color = 0x00FF00
            my_perc_str += '+'
            my_price_str += '+'
        my_price_str += str(round(diff, 2))
        my_perc_str += str(round(perc_change, 4)) + '%'
        thumb_str = 'https://s3.polygon.io/logos/' + ticker.lower() + '/logo.png'
        if ticker == 'MSFT':
            thumb_str = 'https://eodhistoricaldata.com/img/logos/US/MSFT.png'
        my_embed = discord.Embed(timestamp=message.created_at, color=my_color)
        my_embed.set_author(name=my_ticker_names[ticker])
        my_embed.set_thumbnail(url=thumb_str)
        my_embed.add_field(name='**'+ticker+'**', value=my_price_str)
        my_embed.add_field(name='**'+str(price)+'**', value=my_perc_str)
        await message.channel.send(embed=my_embed)
    else:
        await message.channel.send('Invalid command!')        

#run the sell command
async def sell_command(message):
    msg = sell_order_regex.match(str(message.content))
    if not is_clock_open():
        await message.channel.send('Market is closed!  Next open is on ' + str(clock.next_open)[:11] + 'at ' + str(clock.next_open)[12:16] + ' UTC ' + str(clock.next_open)[-6:])
        return
    if msg != None:
        price = 0.00
        my_prices = get_prices()
        ticker = msg.group(1).upper()
        try:
            price = my_prices[ticker]
        except KeyError:
            await message.channel.send('Invalid ticker! Please use !sell <ticker> <amount> using a valid ticker')
            return
        val = -1
        try:
            val = int(msg.group(2))
        except ValueError:
            await message.channel.send('Invalid amount! Please use !sell <ticker> <amount> using a valid amount')
            return
        info = get_account_info(message.author.id)
        positions = info['positions']
        if ticker in positions:
            amount = int(positions[ticker]['amount'])
            amount_balance = float(positions[ticker]['balance'])
            account_balance = float(info['balance'])
            avg_price = amount_balance / amount
            if val <= amount:
                total_sell_price = val * float(price)
                if val == amount:
                    del positions[ticker]
                gain_per_share = round(float(price) - avg_price, 2)
                amount -= val
                amount_balance -= total_sell_price
                my_message = 'Sell Order Executed! ' + str(val) + ' shares of ' + ticker + ' were sold for $' + str(price) + ' each, for a '
                if gain_per_share < 0:
                    my_message += 'loss'
                else:
                    my_message += 'gain'
                my_message += ' of $' + str(abs(gain_per_share)) + ' per share, or ' + str(abs(gain_per_share * val)) + ' total ( ' + str(round(100.0*(gain_per_share/avg_price), 2)) + '% )'
                await message.channel.send(my_message)
                if positions:
                    if amount:
                        positions[ticker]['amount'] = amount
                        positions[ticker]['balance'] = amount_balance
                accounts[str(message.author.id)]['positions'] = positions
                accounts[str(message.author.id)]['balance'] = account_balance + total_sell_price
                write_account_info()
            else:
                await message.channel.send(message.author.name + ' only owns ' + str(positions[ticker]['amount']) + ' shares of ' + ticker + ', cannot sell ' + str(val) + ' shares!')
        else:
            await message.channel.send(message.author.name + ' does not own any positions in ' + ticker + '!')
    else:
        await message.channel.send('Invalid command! Please use !sell <ticker> <amount>')

#run the buy command
async def buy_command(message):
    msg = buy_order_regex.match(str(message.content))
    if not is_clock_open():
        await message.channel.send('Market is closed!  Next open is on ' + str(clock.next_open)[:11] + 'at ' + str(clock.next_open)[12:16] + ' UTC ' + str(clock.next_open)[-6:])
        return
    if msg != None:
        price = 0.00
        my_prices = get_prices()
        ticker = msg.group(1).upper()
        try:
            price = my_prices[ticker]
        except KeyError:
            await message.channel.send('Invalid ticker! Please use !buy <ticker> <amount> using a valid ticker')
        val = -1
        try:
            val = int(msg.group(2))
        except ValueError:
            await message.channel.send('Invalid amount! Please use !buy <ticker> <amount> using a valid amount')
            return
        total_value = price * val
        info = get_account_info(message.author.id)
        positions = info['positions']
        account_balance = float(info['balance'])
        if total_value > account_balance:
            await message.channel.send('Not enough funds, account balance is $' + str(account_balance) + ', but this trade requires $' + str(total_value))
            return
        else:
            if ticker in positions:
                positions[ticker]['amount'] += val
                positions[ticker]['balance'] += total_value
            else:
                positions[ticker] = {}
                positions[ticker]['amount'] = val
                positions[ticker]['balance'] = total_value
            accounts[str(message.author.id)]['positions'] = positions
            accounts[str(message.author.id)]['balance'] = account_balance - total_value
            write_account_info()
            await message.channel.send('Buy Order executed! ' + str(val) + ' shares of ' + ticker + ' were purchased for $' + str(price) + ' each!')
    else:
        await message.channel.send('Invalid command! Please use !buy <ticker> <amount>')

#make the graph
def make_graph(info, all_delta, user, debug):
    dates = []
    for date in info['history']['weekday']:
        dates += [date]
    dates.sort(key=process_date)
    put_on_end_x = []
    put_on_end_y = []
    graph_x = []
    graph_y = []
        
    for d in dates:
        my_price = info['history']['weekday'][d]
        my_date_r = week_format_regex.match(d)
        week_day = my_date_r.group(1)
        hour = my_date_r.group(2)
        minute = my_date_r.group(3)
        cur_week_day = str(datetime.today().weekday())
        cur_hour = str(datetime.now().hour)
        cur_min = str(datetime.now().minute)
        if cur_week_day == week_day:
            if (hour < cur_hour or (hour == cur_hour and minute < cur_min)):
                put_on_end_x += [d]
                put_on_end_y += [my_price]
        else:
            graph_x += [d]
            graph_y += [my_price]
    graph_x += put_on_end_x
    graph_y += put_on_end_y
    if debug:
        i = 0
        for date_s in graph_x:
            print(date_s + ": " + str(graph_y[i]))
            i = i + 1
    fig = plt.figure()
    ax = fig.add_subplot()
    if all_delta >= 0.0:
        ax.plot(graph_x, graph_y, color='g', linewidth=3)
    else:
        ax.plot(graph_x, graph_y, color='r', linewidth=3)
    ax.set_xticks([]) 
    ax.set_yticks([])
    ax.spines['top'].set_visible(True)
    ax.spines['right'].set_visible(True)
    ax.spines['left'].set_visible(True)
    ax.spines['bottom'].set_visible(True)
    path = './graphs/' + str(user.name) + '.png'
    plt.savefig(path, bbox_inches='tight', transparent=True, dpi=100)
    plt.close(fig)
    return path

#run the account command
async def account_command(message):
    user = message.author
    debug = False
    if message.author.id == 97563473105387520:
        if message.content == '!account debug':
            debug = True
    if len(message.mentions) > 1:
        msg = "Error, please do not mention more than one user at a time!"
        await message.channel.send(msg)
        return
    elif len(message.mentions) == 1:
        user = message.mentions[0]
    info = get_account_info(user.id)
    total_account_value = info['balance']
    my_prices = get_prices()
    my_stocks_str = ''
    total_delta = 0.0
    for p in info['positions']:
        amount = info['positions'][p]['amount']
        pos_balance = info['positions'][p]['balance']
        cur_price = my_prices[p]
        total_account_value += amount * cur_price
        if clock.is_open:
            price_day = api.get_barset(p, 'day', limit=1)[p][0].c
        else:
            price_day = api.get_barset(p, 'day', limit=2)[p][0].c
            
        delta = cur_price - price_day
        total_delta += delta * amount    
        if delta > 0.0:
            my_stocks_str += '🟢 '
            my_delta = '+' + str(round(delta, 2))
            my_perc = '+' + str(round(((delta/price_day)*100.0), 2))
        else:
            my_stocks_str += '🔴 '
            my_delta = str(round(delta, 2))
            my_perc = str(round(((delta/price_day)*100.0), 2))
        if (cur_price*amount) - pos_balance > 0.0:
            my_bal = '+' + str(round(cur_price*amount - pos_balance, 2))
            my_perc_ch = '+' + str(round((cur_price*amount - pos_balance) / (cur_price*amount), 2))
        else:
            my_bal = str(round(cur_price*amount - pos_balance, 2))
            my_perc_ch = str(round((cur_price*amount - pos_balance) / (cur_price*amount), 2))
        my_stocks_str += '**' + p + ' | ' + my_delta + '  (' + my_perc + '%)**\n'
        my_stocks_str += '*' + str(amount) + ' Positions | ' + my_bal + '  (' + my_perc_ch + '%)*\n'
    if total_delta > 0.0:
        my_color = 0x00FF00
        my_tot_delta = '+'+ str(round(total_delta, 2))
    else:
        my_color = 0xFF0000
        my_tot_delta = str(round(total_delta, 2))
    all_delta = total_account_value - 1000000
    if all_delta > 0.0:
        my_all_delta = '+' + str(round(all_delta, 2))
    else:
        my_all_delta = str(round(all_delta, 2))

  
    path = make_graph(info, all_delta, user, debug)
    my_image = discord.File(path, filename='image.png')

    my_stocks_str += '\n**BUYING POWER | ' + str(round(info['balance'], 2)) +'**\n'
    my_stocks_str += '**ACCOUNT VALUE | ' + str(round(total_account_value, 2)) + '  ( ' + my_tot_delta + ' Day )  ( ' + my_all_delta + ' Ovr )**\n'
    my_embed = discord.Embed(timestamp=message.created_at, color=my_color, description=my_stocks_str)
        
    my_embed.set_image(url='attachment://image.png')
    my_embed.set_author(name='TRADING ACCOUNT SUMMARY -- ' + str(user.name).upper())
    await message.channel.send(embed=my_embed, file=my_image)
    os.remove(path)

#run watchlist command
async def watch_command(message):
    if (str(message.content) == '!watch'):
        info = get_account_info(message.author.id)
        if 'watch' in info:
            await message.channel.send("Watchlist for " + str(message.author) + ": " + str(info['watch']))
            return
        else:
            await message.channel.send(str(message.author) + " has no watchlist!\nPlease type '!watch <ticker> <price in $>' to add a ticker to your watchlist")
            return
    msg = watch_regex.match(str(message.content))
    if msg != None:
        #grab the ticker and coerce it to all upppercase
        my_prices = get_prices()
        ticker = msg.group(1).upper()
        price = 0.00
        try:
            price = my_prices[ticker]
        except KeyError:
            await message.channel.send('Invalid ticker! Please use !watch <ticker> <price in $>')
            return
        price = msg.group(2)
        if price != None:
            val = -1
            try:
                val = round(float(price),2)
                info = get_account_info(message.author.id)
                if val == 0.0:
                    if ticker in info['watch']:
                      del info['watch'][ticker]
                      await message.channel.send('Removed ' + ticker + ' from watchlist\nCurrent watchlist for ' + str(message.author) + ": " + str(info['watch']))
                      write_account_info()
                      return
                    else:
                      await message.channel.send("Cannot remove "  + ticker + " from watchlist because it is not already on the watchlist\nCurrent watchlist for " + str(message.author) + ": " + str(info['watch']))
                      return
                info['watch'][ticker] = val
                await message.channel.send('Now watching ' + ticker + '\nCurrent watchlist for ' + str(message.author) + ': ' + str(info['watch']))
                write_account_info()
                return
            except ValueError:
                await message.channel.send('Invalid price! Please use !watch <ticker> <price in $>')
                return
            except KeyError as e:
                print(str(message.author) + ' did not have the '  + str(e) + ' table, adding now...')
                info['watch'] = {}
                write_account_info()
    else:
        await message.channel.send('Invalid command! Please use !watch <ticker> <price in $>')

#log servers that bot connects to on startup
@client.event
async def on_ready():
    for my_server in client.guilds:
        print('Bot connected to discord on server: ' + str(my_server))
        
#listens for and matches specific messages (the important bit)
@client.event
async def on_message(message):
    #if the author of the message is the client user, ignore it 
    #(this prevents the bot reacting to messages that it itself sends)
    if message.author == client.user:
        return 
    #price command
    if '!help' in message.content:
        my_message = "```'!account [@mention]': Displays account balance, buying power, currently held positions, and a graph of the past week's account balance history\n\t-Optionally display the account info of another user on this server using their @mention tag\n\n```" + \
        "```'!buy <ticker> <amount>': If able, purchases the requested amount of shares of the provided ticker for its current market price\n\n```" + \
        "```'!sell <ticker> <amount>': If able, sells the requested amount of shares of the provided ticker from your portfolio at the current market price\n\n```" + \
        "```'!price <ticker>': Get the current market price of a given ticker\n\n```" + \
        "```'!watch [<ticker> <price>]': Displays your current watchlist or add a ticker to your watchlist by providing the ticker and the price you want to watch for\n\t-A positive price means you want to get an alert when that ticker rises above the provided price\n\t-A negative price means you want to get an alert for when that ticker drops below the provided price\n\t-A price of 0 will remove the ticker from the watchlist```\n" + \
        "\n**__All ticker names and prices are referenced from NASDAQ__**"
        my_embed = discord.Embed(timestamp=message.created_at, color=0x33abf9, description=my_message)
        my_embed.set_author(name='EV-9D9 COMMAND LIST')
        await message.channel.send(embed=my_embed)
        #await message.channel.send(my_message)
    elif '!price' in message.content:
        await price_command(message)
    elif '!sell' in message.content:
        await sell_command(message)
    elif '!buy' in message.content:
        await buy_command(message)
    elif '!account' in message.content:
        await account_command(message)
    elif '!history' in message.content:
        if message.author.id != 97563473105387520:
          await message.channel.send("Only PAU can do this")
          return
        info = get_account_info(message.author.id)
        for entry in info['history']:
          await message.channel.send(str(entry))
          for entry2 in info['history'][entry]:
            await message.channel.send(entry2 + ": " + str(info['history'][entry][entry2]))
    elif '!watch' in message.content:
        await watch_command(message)      

async def start_discord_client():
    return await client.start(TOKEN)

if __name__ == '__main__':
    start_discord_client()
