import asyncio
import threading
import time
import logging
import sys
import pandas as pd
from kiteconnect import KiteConnect, KiteTicker
import datetime
from collections import defaultdict
from asyncio import Lock
import constants
import requests


# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KiteDataEngine:
    def __init__(self):
        self.access_token = self._get_access_token()
        self.logger = logging.getLogger('MarketData')
        self.kite = KiteConnect(api_key="s4pnzfflytntrgmf")
        self.kite.set_access_token(self.access_token)

    def _get_access_token(self):
        response = requests.get(constants.URL_CREDENTIAL_API_ZEORDHA_TOKEN)
        if response.status_code == 200:
            return response.json()

class SpotCandleEngine:
    def __init__(self, kite, symbol, loop):
        self.kite = kite
        self.symbol = symbol
        self.loop = loop  # The asyncio event loop
        self.logger = logging.getLogger('SpotCandleEngine')

        self.df_spot = pd.DataFrame()
        self.spot_instrument_token = None

        # Asynchronous queue to hold ticks
        self.tick_queue = asyncio.Queue()
    
    def map_symbol_to_spot(self):
        symbol_mapping = {
            'NIFTY 50': 'NIFTY',
            'NIFTY BANK': 'BANKNIFTY',
            # Add other mappings if needed
        }
        return symbol_mapping.get(self.symbol, self.symbol)
    


    async def fetch_ohlc_once(self, token):
        '''Fetch OHLC data once for the spot instrument.'''
        try:
            # Define desired time range
            desired_start_time = datetime.time(9, 15)
            desired_end_time = datetime.time(15, 30)

            # Get current time
            now = datetime.datetime.now()

            # Floor the current time to the last completed 15-minute interval
            minute = (now.minute // 15) * 15
            end_datetime = now.replace(minute=minute, second=0, microsecond=0)

            # If the current time is exactly on a 15-minute mark, subtract 15 minutes to get the last completed candle
            # if now.minute % 15 == 0 and now.second == 0:
            #     end_datetime -= datetime.timedelta(minutes=15)

            # Calculate start datetime for fetching data
            start_datetime = end_datetime - datetime.timedelta(days=constants.DF_15MIN_BACK_DAYS)

            # Format datetime strings for the API
            start_time_str = start_datetime.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_datetime.strftime('%Y-%m-%d %H:%M:%S')

            self.logger.debug(f"Fetching OHLC data from {start_time_str} to {end_time_str}")

            # Fetch historical data
            ohlc_data = self.kite.historical_data(
                instrument_token=token,
                from_date=start_time_str,
                to_date=end_time_str,
                interval='15minute'
            )
            
            # Convert to DataFrame
            df_ohlc = pd.DataFrame(ohlc_data)
            
            if df_ohlc.empty or df_ohlc is None:
                self.logger.warning("No OHLC data fetched from the API.")
                return None
            
            # Rename columns
            df_ohlc.rename(columns={
                'date': 'Datetime',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            
            # Convert 'Datetime' to datetime objects without timezone
            df_ohlc['Datetime'] = pd.to_datetime(df_ohlc['Datetime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
            
            # Remove any rows with NaT in 'Datetime'
            initial_len = len(df_ohlc)
            df_ohlc = df_ohlc.dropna(subset=['Datetime'])
            dropped_len = initial_len - len(df_ohlc)
            if dropped_len > 0:
                self.logger.warning(f"Dropped {dropped_len} rows due to invalid 'Datetime' format.")
            
            # Remove microseconds if any
            df_ohlc['Datetime'] = df_ohlc['Datetime'].dt.floor('S')
            
            # Debugging: Inspect the 'Datetime' column after parsing
            self.logger.debug(f"Sample 'Datetime' after parsing:\n{df_ohlc['Datetime'].head()}")

            # Create separate 'Date' and 'Time' columns
            df_ohlc['Date'] = df_ohlc['Datetime'].dt.date
            df_ohlc['Time'] = df_ohlc['Datetime'].dt.time

            # Apply explicit time-based filter
            mask = (df_ohlc['Time'] >= desired_start_time) & (df_ohlc['Time'] <= desired_end_time)
            df_filtered = df_ohlc[mask]

            # Debugging: Verify no rows are outside the desired time range
            num_excluded = len(df_ohlc) - len(df_filtered)
            self.logger.info(f"Excluded {num_excluded} rows outside the desired time range.")

            # Additionally, drop rows where 'Open' is 0.0, assuming these are invalid or placeholder entries
            df_filtered = df_filtered[df_filtered['Open'] != 0.0]
            num_zero_open = (df_filtered['Open'] == 0.0).sum()
            if num_zero_open > 0:
                self.logger.info(f"Dropped {num_zero_open} rows where 'Open' is 0.0.")
                df_filtered = df_filtered[df_filtered['Open'] != 0.0]

            # Drop 'Date' and 'Time' columns as they were only for filtering
            df_filtered.drop(['Date', 'Time'], axis=1, inplace=True)
            
            # Optional: Sort the DataFrame by 'Datetime' if not already sorted
            df_filtered.sort_values('Datetime', inplace=True)

            # Optional: Reset index for a clean integer index
            df_filtered.reset_index(drop=True, inplace=True)

            # Ensure the 'Datetime' column is in 'YYYY-MM-DD HH:MM:SS' format as strings
            df_filtered['Datetime'] = df_filtered['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')

            self.logger.info(f'OHLC Spot Data that is fetched: {df_ohlc}')
            self.df_spot = df_filtered


            return df_filtered  # Return the filtered DataFrame

        except Exception as e:
            self.logger.error(f"Failed to fetch OHLC for spot: {e}")
            return None
                    
    async def update_dataframe_15min_ohlc(self, df_ohlc):
        '''Update or resample the OHLC data to 15-minute intervals.'''
        self.df_spot = df_ohlc  # Updating the existing DataFrame with new data

    def get_spot_instrument_token(self):
        '''Fetch the instrument token for the given spot symbol.'''
        # mapped_symbol = self.map_symbol_to_spot()
        instruments = self.kite.instruments("NSE")
        for instrument in instruments:
            if instrument['tradingsymbol']==self.symbol:
                self.spot_instrument_token = instrument['instrument_token']
                self.logger.info(f"Spot instrument token for {self.symbol}: {self.spot_instrument_token}")
                return self.spot_instrument_token
        self.logger.error(f"Instrument token for {self.symbol} not found.")

    def format_tick(self, tick):
        '''Format the tick data into a DataFrame row.'''
        data = {
            'Datetime': tick['exchange_timestamp'],
            'Open': tick['ohlc']['open'],
            'High': tick['ohlc']['high'],
            'Low': tick['ohlc']['low'],
            'Close': tick['ohlc']['close'],
        }
        return pd.DataFrame([data])

    async def process_ticks(self):
        '''Asynchronously process ticks from the queue and update the DataFrame.'''
        while True:
            tick = await self.tick_queue.get()
            formatted_df = self.format_tick(tick)
            self.df_spot = pd.concat([self.df_spot, formatted_df], ignore_index=True)
            self.tick_queue.task_done()
            # Optional: Limit the size of df_spot to prevent memory issues
            if len(self.df_spot) > 10000:
                self.df_spot = self.df_spot.iloc[-5000:]

    async def resample_ohlc(self, interval='15min'):
        '''Resample the full OHLC data to the specified time interval.'''
        if self.df_spot.empty or self.df_spot is None:
            self.logger.warning("df_spot is empty. No data to resample.")
            return pd.DataFrame()
        
        df = self.df_spot.copy()
        
        # Convert 'Datetime' to datetime objects
        df['Datetime'] = pd.to_datetime(df['Datetime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        df = df.dropna(subset=['Datetime'])
        
        # Set 'Datetime' as index
        df.set_index('Datetime', inplace=True)
        
        # Define OHLC aggregation
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last'
        }
        
        # Resample
        ohlc_df = df.resample(interval).agg(ohlc_dict)
        
        # Drop intervals with no data
        ohlc_df = ohlc_df.dropna()
        
        # Reset index
        ohlc_df.reset_index(inplace=True)
        
        return ohlc_df
    async def get_latest_15min_candle(self):
        '''Retrieve the latest 15-minute candle.'''
        resampled_df =  await self.resample_ohlc()
        if not resampled_df.empty:
            latest_candle = resampled_df.iloc[-1]
            self.logger.info(f"Latest 15-minute candle: {latest_candle}")
            return latest_candle
        else:
            self.logger.warning("No candles available.")
            return None

    def on_tick(self, tick):
        '''Callback function to handle tick data.'''
        asyncio.run_coroutine_threadsafe(self.tick_queue.put(tick), self.loop)

    def start(self):
        '''Start the asynchronous tick processing task.'''
        asyncio.ensure_future(self.process_ticks(), loop=self.loop)

class OptionsCandleEngine:
    def __init__(self, kite, spot_symbol, loop, strike_step=50, strike_range=20):
        self.kite = kite
        self.spot_symbol = spot_symbol
        self.strike_step = strike_step
        self.strike_range = strike_range
        self.loop = loop  # The asyncio event loop
        self.logger = logging.getLogger('OptionsCandleEngine')

        self.df_options = pd.DataFrame()
        self.options_tokens = []
        self.instrument_lookup = {}
        self.exchange_token_mapping = {}  # Initialize the exchange_token_mapping
        self.tick_buffer = defaultdict(list)  # Buffer to store ticks before processing

        # Asynchronous queue to hold ticks
        self.tick_queue = asyncio.Queue()
        self.last_prices = {} 

        # Async lock to ensure proper access control
        self.lock = asyncio.Lock()  # Add a lock

    def map_symbol_to_options(self):
        '''Map spot symbols to corresponding options symbols.'''
        symbol_mapping = {
            'NIFTY 50': 'NIFTY',
            'NIFTY BANK': 'BANKNIFTY',
            'NIFTY MID SELECT': 'MIDCPNIFTY',
            'NIFTY FIN SERVICE': 'FINNIFTY'
        }
        return symbol_mapping.get(self.spot_symbol, self.spot_symbol)

    def get_closest_expiry(self, df_instruments, options_symbol):
        '''Get the closest expiry date for the given options symbol.'''
        df_symbol = df_instruments[df_instruments['tradingsymbol'].str.startswith(options_symbol) & (~df_instruments['tradingsymbol'].str.contains('NXT'))]
        df_symbol = df_symbol.sort_values('expiry')
        closest_expiry = df_symbol['expiry'].iloc[0] if not df_symbol.empty else None
        if closest_expiry:
            self.logger.info(f"Closest expiry for {options_symbol}: {closest_expiry}")
        else:
            self.logger.error(f"Failed to find any expiry for {options_symbol}")
        return closest_expiry
    
    async def get_instruments_df(self):
        '''Fetch all instruments from the Kite API.'''
        try:
            instruments = self.kite.instruments("NFO")
            df_instruments = pd.DataFrame(instruments)
            self.logger.info(f"Fetched {len(df_instruments)} instruments from NFO segment.")
            return df_instruments
        except Exception as e:
            self.logger.error(f"Failed to fetch instruments: {e}")
            return pd.DataFrame()
    


    def get_formatted_masters(self, symbol, strike_step=100):
        '''Fetch and format master data (option contracts) from the Kite API.'''
        try:
            instruments = self.kite.instruments("NFO")  # Fetch all instruments from the NFO segment
            df_instruments = pd.DataFrame(instruments)

            # Log the shape of the instrument dataframe to check if data is available
            self.logger.info(f"Fetched {len(df_instruments)} instruments from NFO segment.")

            # Filter by symbol and option type (CE, PE) and exclude entries where the strike is 0.0
            options_symbol = self.map_symbol_to_options()
            # Get the closest expiry for the symbol
            closest_expiry = self.get_closest_expiry(df_instruments, options_symbol)
            df_instruments = df_instruments[
                (df_instruments['tradingsymbol'].str.startswith(options_symbol)) &  # Match the symbol
                (df_instruments['expiry'] == closest_expiry) &                      # Match the expiry date
                (df_instruments['segment'] == 'NFO-OPT') &                          # Ensure it is an options contract
                (df_instruments['instrument_type'].isin(['CE', 'PE']))              # Ensure it is Call (CE) or Put (PE)
            ]

            if df_instruments.empty:
                self.logger.error(f"No valid instruments found for {symbol} options (CE/PE).")
                return pd.DataFrame()

            # Log the formatted instrument dataframe for debugging
            self.logger.info(f"Formatted instruments for {symbol}:\n{df_instruments.head()}")

            return df_instruments
        except Exception as e:
            self.logger.error(f"Failed to fetch and format master data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _form_instrument_strike_map(self, df_instruments, strike_prices):
        '''Map strike prices to the instrument token for each Call (CE) and Put (PE) option.'''
        try:
            # Create a dictionary to map strike prices to instrument tokens
            self.map_strike_instrument = {}
            self.instrument_token_to_exchange_token = {}  # New dictionary to map instrument_token to exchange_token

            for strike in strike_prices:
                for option_type in ['CE', 'PE']:
                    # Filter DataFrame for the given strike and option type
                    filtered_df = df_instruments[(df_instruments['strike'] == strike) & (df_instruments['instrument_type'] == option_type)]

                    if not filtered_df.empty:
                        exchange_token = filtered_df['exchange_token'].values[0]
                        instrument_token = filtered_df['instrument_token'].values[0]
                        self.map_strike_instrument[(strike, option_type)] = exchange_token
                         # Map instrument_token to exchange_token
                        self.instrument_token_to_exchange_token[instrument_token] = exchange_token
                        self.logger.info(f"Mapped strike {strike} {option_type} to exchange_token {exchange_token} and instrument_token {instrument_token}")
                    else:
                        self.logger.warning(f"No instrument found for strike {strike} {option_type}")
        except Exception as e:
            self.logger.error(f"Failed to form instrument strike map: {e}")

    async def get_options_instruments(self):
        '''Retrieve and map options instruments for the given symbol and strike range.'''
        options_symbol = self.map_symbol_to_options()
        df_instruments = self.get_formatted_masters(symbol=options_symbol, strike_step=self.strike_step)

        # Get the closest expiry for the options
        closest_expiry = self.get_closest_expiry(df_instruments, options_symbol)
        if closest_expiry is None:
            self.logger.error(f"No expiry found for {options_symbol}.")
            return

        # Filter instruments for the closest expiry date
        df_filtered = df_instruments[df_instruments['expiry'] == closest_expiry]

        # Log the filtered instruments to debug if they match the expiry
        self.logger.info(f"Filtered instruments for expiry {closest_expiry}:\n{df_filtered.head()}")

        # Get the current spot price and generate the strike prices around the spot price
        spot_ltp = self.kite.ltp(f"NSE:{self.spot_symbol}")[f"NSE:{self.spot_symbol}"]['last_price']
        spot_price_rounded = round(spot_ltp / self.strike_step) * self.strike_step

        # Generate a list of strike prices around the spot price
        strike_prices = [spot_price_rounded + i * self.strike_step for i in range(-self.strike_range, self.strike_range + 1)]

        # Map the strike prices to instrument tokens
        self._form_instrument_strike_map(df_filtered, strike_prices)

        # Filter instruments
        filtered_df = df_instruments[
            (df_instruments['tradingsymbol'].str.startswith(options_symbol)) &
            (df_instruments['expiry'] == closest_expiry) &
            (df_instruments['strike'].isin(strike_prices)) &
            (df_instruments['instrument_type'].isin(['CE', 'PE'])) &
            (df_instruments['segment'] == 'NFO-OPT')
        ]

        # Add exchange_token mapping
        for _, row in filtered_df.iterrows():
            self.instrument_token_to_exchange_token[row['instrument_token']] = row['exchange_token']
            self.instrument_lookup[row['instrument_token']] = {'expiry': row['expiry']}

        self.options_tokens = [int(token) for token in filtered_df['instrument_token'].tolist()]

        self.instrument_lookup.update(filtered_df.set_index('instrument_token').to_dict('index'))

        if not self.options_tokens:
            self.logger.error(f"No valid option tokens found for {self.spot_symbol}.")
        else:
            self.logger.info(f"Valid options tokens for {self.spot_symbol}: {self.options_tokens}")


        self.logger.info(f"Retrieved {len(self.options_tokens)} options tokens for {options_symbol}")
        self.logger.info(f"Strike-instrument mapping: {self.map_strike_instrument}")

    async def fetch_options_ohlc(self):
        '''Fetch OHLC data once for the options.'''
        try:
            start_time = datetime.datetime.now().replace(hour=9, minute=15, second=0)
            end_time = datetime.datetime.now().replace(hour=16, minute=0, second=0)

            for token in self.options_tokens:
                ohlc_data = self.kite.historical_data(
                    instrument_token=token,
                    from_date=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    to_date=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    interval='15minute'
                )
                df_ohlc = pd.DataFrame(ohlc_data)
                self.df_options = pd.concat([self.df_options, df_ohlc], ignore_index=True)

            self.logger.info(f"Fetched OHLC for options {self.spot_symbol}.")
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLC for options: {e}")

    def format_tick(self, tick):
        '''Format the tick data into a DataFrame row using exchange_token and expiry.'''
       

        data = {
            'Datetime': tick['last_trade_time'],
            'Open': tick['ohlc']['open'],
            'High': tick['ohlc']['high'],
            'Low': tick['ohlc']['low'],
            'Close': tick['ohlc']['close'],
        }
        return pd.DataFrame([data])

    

    def resample_ohlc(self, interval='15min'):
        '''Resample the full OHLC data for options based on time intervals.'''
        df = self.df_options.copy()
        
        # Ensure Datetime column is in correct format and drop rows with invalid dates
        df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
        df = df.dropna(subset=['Datetime'])
        
        # Set Datetime as index for resampling
        df.set_index('Datetime', inplace=True)

        # Resampling configuration for OHLC data
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last'
        }

        if not df.empty:
            # Resample based on the interval and aggregate using the OHLC dictionary
            ohlc_df = df.resample(interval).agg(ohlc_dict)
            ohlc_df.reset_index(inplace=True)
            return ohlc_df
        else:
            return pd.DataFrame()  # Return an empty DataFrame if no data is available

    def get_latest_15min_candles(self):
        '''Retrieve the latest 15-minute candles for all options.'''
        # Resample the data to 15-minute intervals
        resampled_df = self.resample_ohlc()

        if not resampled_df.empty:
            # Get the last row (latest candle) for each group of data
            latest_candles = resampled_df.tail(1)  # Only interested in the last candle
            self.logger.info(f"Latest 15-minute candles:\n{latest_candles}")
            return latest_candles
        else:
            self.logger.warning("No candles available.")
            return None
    
   

    def get_tradingsymbol_from_token(self, token):
        """
        Fetch the tradingsymbol from the instrument token using the Zerodha API.

        Args:
            token (int): The instrument token.

        Returns:
            str: The tradingsymbol corresponding to the token.
        """
        try:
            instruments = self.kite.instruments('NFO')  # Fetch all NFO instruments
            for instrument in instruments:
                if instrument['instrument_token'] == token:
                    return instrument['tradingsymbol']
            return None  # Return None if the token is not found
        except Exception as e:
            self.logger.error(f"Failed to fetch instruments: {e}")
            return None


    def update_option_tokens(self, tokens):
        '''Update the list of option tokens to track.'''
        self.options_tokens = tokens
        self.logger.info(f"Updated tracked tokens: {self.options_tokens}")


    async def get_current_market_price(self, exchange_token):
        """
        Fetch the current market price (LTP) for a given exchange token asynchronously.

        Args:
            exchange_token (int): The exchange token for the options contract.

        Returns:
            float: The last traded price (LTP) of the options token, or None if no tick data is available.
        """
        try:
            # Wait until a tick with the relevant exchange_token is processed
            # while exchange_token not in self.last_prices:
            #     await asyncio.sleep(0.1)  # Polling until price is available
            
            price = self.last_prices[exchange_token]
            if price is not None:
                return price
            else:
                self.logger.warning(f"No price data available for token {exchange_token}")
            
        except Exception as e:
            self.logger.error(f"Failed to fetch current market price for token {exchange_token}: {e}")
            return None

    def on_tick(self, tick):
        '''Callback function to handle tick data.'''
        
        instrument_token = tick['instrument_token']
        # Use the instrument_token to find the corresponding exchange_token
        exchange_token = self.instrument_token_to_exchange_token.get(instrument_token, None)
        
        if exchange_token is not None:
            # Convert to int only if exchange_token is valid
            exchange_token = int(exchange_token)
            
            # Update last_prices immediately to ensure access by stoplossBrain
            self.last_prices[exchange_token] = tick['last_price']
            # self.logger.info(f"Updated last price for token {exchange_token}: {tick['last_price']}")

            # Format the tick data and update the df_options DataFrame
            formatted_df = self.format_tick(tick)
            self.df_options = pd.concat([self.df_options, formatted_df], ignore_index=True)

            # Optionally, limit the size of df_options to prevent memory issues
            if len(self.df_options) > 10000:
                self.df_options = self.df_options.iloc[-5000:]

            # Log the available prices in the dictionary to see if prices are updated correctly
            # self.logger.info(f"Current last prices: {self.last_prices}")
        else:
            self.logger.warning(f"Received tick for unrecognized instrument_token: {instrument_token}")

    # def start(self):
    #     '''Start the tick data subscription or any necessary initialization.'''
    #     # Initialize any connections, subscriptions, or set up the environment
    #     self.logger.info("Starting tick subscription for options tokens.")
        
    #     # Example: If you're subscribing to tick data
    #     tokens_to_subscribe = self.options_tokens  # Assuming options_tokens contains the tokens you want to subscribe to
    #     self.kite.subscribe(tokens_to_subscribe)
    #     self.logger.info(f"Subscribed to tokens: {tokens_to_subscribe}")

    # def start(self):
    #     '''Start the asynchronous tick processing task.'''
    #     asyncio.ensure_future(self.on_tick(), loop=self.loop)




class MarketDataStreamer:
    def __init__(self, kite, spot_engine, options_engine, loop):
        self.kite = kite
        self.spot_engine = spot_engine
        self.options_engine = options_engine
        self.loop = loop
        self.logger = logging.getLogger('MarketDataStreamer')
        self.kws = KiteTicker(kite.api_key, kite.access_token)
        self.instrument_tokens = []
        self.setup_callbacks()

    def setup_callbacks(self):
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.kws.on_error = self.on_error

    def on_ticks(self, ws, ticks):
        '''Handle received ticks and dispatch them to the respective engines.'''
        # self.logger.info(f"Received ticks: {ticks}")
        
        for tick in ticks:
            token = tick['instrument_token']
            # exchange_token = tick['exchange_token']
            # self.logger.info(f"Received tick for token: {token}")
            # self.logger.info(f'Spot instrument token is {self.spot_engine.spot_instrumen_token}\n Options instrument token are {self.options_engine.options_tokens}')
            # Dispatch ticks to the respective engine based on the token
            if token == self.spot_engine.spot_instrument_token:
                self.spot_engine.on_tick(tick)
            elif token in self.options_engine.options_tokens:
                # self.logger.info(f"Dispatching tick to Options Engine for token: {token}")
                self.options_engine.on_tick(tick)
            else:
                self.logger.warning(f"Received tick for unrecognized token: {token}")

    def on_connect(self, ws, response):
        '''Subscribe to all instrument tokens when WebSocket is connected.'''
        self.logger.info("WebSocket connected. Subscribing to tokens.")
        if not self.spot_engine.spot_instrument_token:
            self.logger.error("Spot instrument token is missing.")
        else:
            self.logger.info(f"Spot token: {self.spot_engine.spot_instrument_token}")
        if not self.options_engine.options_tokens:
            self.logger.error("No options tokens found.")
        self.instrument_tokens = [self.spot_engine.spot_instrument_token] + self.options_engine.options_tokens
        self.logger.info(f"Subscribing to tokens: {self.instrument_tokens}")
        ws.subscribe(self.instrument_tokens)
        ws.set_mode(ws.MODE_FULL, self.instrument_tokens)
        self.logger.info("Subscription request sent for all tokens.")

    def on_close(self, ws, code, reason):
        '''Handle WebSocket close event.'''
        self.logger.error(f"WebSocket closed with code: {code}, reason: {reason}")

    def on_error(self, ws, code, reason):
        '''Handle WebSocket error.'''
        self.logger.error(f"WebSocket error: {code}, reason: {reason}")

    

    def start(self):
        '''Start the WebSocket connection using the threaded parameter.'''
        self.logger.info("Starting market data stream.")
        self.kws.connect(threaded=True)
        self.logger.info("Market data stream started.")

    def stop(self):
        '''Stop the WebSocket connection.'''
        self.kws.stop()
        self.logger.info("Market data stream stopped.")

# # Main script
# if __name__ == '__main__':
#     # Replace with your actual credentials and paths
#     API_KEY = "s4pnzfflytntrgmf"
#     API_SECRET = "tmnkkkdk2k98oqp29pks73yci4t231o6"
#     TOTP_SECRET = "CLHLMHAJKIVDDRXA6BFXM3UNUOYAU7EK"
#     USER_ID = 'LEY228'
#     PASSWORD = 'Dell@123'
#     DRIVER_PATH = r"D:\\HirakDrive\\workspace\\GitHub\\Zerodha integration\\chromedriver-win64\\chromedriver.exe"

#     # Initialize the KiteDataEngine
#     data_engine = KiteDataEngine(
#         api_key=API_KEY,
#         api_secret=API_SECRET,
#         totp_secret=TOTP_SECRET,
#         userid=USER_ID,
#         password=PASSWORD,
#         driver_path=DRIVER_PATH
#     )

#     # Log in and initialize the API
#     data_engine.login_and_initialize()
#     kite = data_engine.kite

#     # Create an asyncio event loop
#     loop = asyncio.get_event_loop()

#     # Initialize SpotCandleEngine
#     spot_engine = SpotCandleEngine(kite, "NIFTY 50", loop)
#     spot_engine.get_spot_instrument_token()
#     spot_engine.start()

#     # Initialize OptionsCandleEngine
#     options_engine = OptionsCandleEngine(kite, "NIFTY 50", loop)
#     options_engine.get_options_instruments()
#     options_engine.start()

#     # Start the Market Data Streamer
#     streamer = MarketDataStreamer(kite, spot_engine, options_engine, loop)
#     streamer.start()

#     # Run the event loop
#     try:
#         loop.run_forever()
#     except KeyboardInterrupt:
#         streamer.stop()
#         loop.stop()
#         spot_engine.logger.info("Shutting down...")
#         options_engine.logger.info("Shutting down...")

#         # Optionally, you can print or save the dataframes here
#         spot_candles = spot_engine.resample_ohlc()
#         options_candles = options_engine.resample_ohlc()

#         print("Final Spot Candles:")
#         print(spot_candles.tail())

#         print("\nFinal Options Candles:")
#         print(options_candles.tail())

