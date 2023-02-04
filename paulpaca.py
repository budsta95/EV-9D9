from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.live import StockDataStream
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import os,re
from dotenv import load_dotenv                                                                                                                           

load_dotenv()

class ALPI:
    def __init__(self):
        self.SHDC = StockHistoricalDataClient(os.getenv('API_KEY'), os.getenv('SECRET_KEY'))
        self.SDS = StockDataStream(os.getenv('API_KEY'), os.getenv('SECRET_KEY'))

    def get_bars(self, tickers, timeframe, start=None, end=None, limit=None):
        if start and end and limit:
            raise RuntimeError("The get_bars method cannot use limit in conjunction with both a start and end value")
        if isinstance(tickers, str):
            tickers = [tickers]

        if timeframe in ['day', 'd', 'days']:
            timeframe = TimeFrame.Day
            if end is None:
                end = datetime.today()
                if limit:
                    start = end - timedelta(days=limit)
            if start is None:
                start = end - timedelta(days=1)
                if limit:
                    end = start + timedelta(days=limit)
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                raise TypeError(f"User provided a start or end value that was not a datetime instance")
            if start > end:
                raise ValueError(f"User-provided start value '{start}' occurs after {end}")
        elif timeframe in ['minute', 'min', 'mins', 'm', 'minutes']:
            timeframe = TimeFrame.Minute
        elif timeframe in ['hour', 'hours', 'h', 'hrs']:
            timeframe = TimeFrame.Hour
        elif timeframe in ['week', 'weeks', 'w', 'wk', 'wks']:
            timeframe = TimeFrame.Week
        elif timeframe in ['month', 'months', 'mth', 'mnth']:
            timeframe = TimeFrame.Month
        else:
            raise TypeError(f"The provided timeframe '{timeframe}' is not a valid time frame")

        SBR = StockBarsRequest(symbol_or_symbols=tickers, timeframe=timeframe, start=start, end=end)
        return self.SHDC.get_stock_bars(SBR)
