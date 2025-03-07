import asyncio
import pandas as pd
from datetime import timedelta
from data_engine import SymphonyFintechAPI
import constants
from logging_config import CustomLogger
from datetime import datetime, timezone
from io import StringIO


class SpotCandleEngine:
    def __init__(self, symphony_api,equity):
        self.logger = CustomLogger('spotCandleEngine', equity = equity)
        self.df_1sec_daily = pd.DataFrame(columns=['Datetime', 'Open', 'High', 'Low', 'Close'])
        self.df_15min = pd.DataFrame(columns=['Datetime', 'Open', 'High', 'Low', 'Close'])
        self.symphony_api = symphony_api
        self.formatted_quote = None
        
        self.spot_instruments = [{
        'exchangeSegment': 2,
        'exchangeInstrumentID': 14732,
        }]

    async def get_df_15min(self):
        return self.df_15min
    
    async def fetch_ohlc_once(self, exchangeSegment='NSECM', exchangeInstrumentID=26000, compressionValue=constants.compression_value_15_min, lookbackDays=constants.DF_15MIN_BACK_DAYS, drop_last=True, subtract_time=True):
        try:
            start_time = (datetime.now().replace(hour=9, minute=15, second=0) - timedelta(days=lookbackDays)).strftime("%b %d %Y %H%M%S")
            end_time = (datetime.now().replace(hour=16, minute=00, second=0)).strftime("%b %d %Y %H%M%S")
            response = self.symphony_api.get_ohlc(exchangeSegment=exchangeSegment, exchangeInstrumentID=exchangeInstrumentID, startTime=start_time, endTime=end_time, compressionValue=compressionValue)
            formatted_df = self.symphony_api.format_ohlc_spot(response, drop_last=drop_last, subtract_time=subtract_time)
            return formatted_df
        except Exception as e:
            self.logger.log_message('error', f"Failed to fetch ohlc once: {e}")

    async def fetch_spot_ohlc(self, exchangeInstrumentID):
        try:
            start_time = (datetime.now().replace(hour=9, minute=15, second=0) - timedelta(days=constants.DF_15MIN_BACK_DAYS)).strftime("%b %d %Y %H%M%S")
            print(start_time)
            end_time = (datetime.now().replace(hour=16, minute=00, second=0)).strftime("%b %d %Y %H%M%S")
            print(end_time)
            response = self.symphony_api.get_ohlc(exchangeSegment='NSECM', exchangeInstrumentID=exchangeInstrumentID, startTime=start_time, endTime=end_time, compressionValue=constants.compression_value_15_min)
            print(response)
            formatted_df = self.symphony_api.format_ohlc_spot(response)
            print(formatted_df)
            await self.update_dataframe_15min_ohlc(formatted_df)
        except Exception as e:
            self.logger.log_message('error', f"Failed to fetch spot ohlc: {e}")


    async def update_dataframe_15min_ohlc(self, df):
        try:
            self.df_15min = df
        except Exception as e:
            self.logger.log_message('error', f"Failed to update dataframe 15min ohlc: {e}")

    # to get the latest 15min candle
    async def get_latest_15min_candle(self):
        try:
            return self.df_15min.iloc[-1]
        except Exception as e:
            self.logger.log_message('error', f"Failed to get latest 15min candle: {e}")


    async def run(self, exchangeInstrumentID):
        try:
            # Start fetching and inserting quotes asynchronously
            print(exchangeInstrumentID)
            await asyncio.gather(
                self.fetch_spot_ohlc(exchangeInstrumentID=exchangeInstrumentID)
            )
        except Exception as e:
            self.logger.log_message('error', f"Failed to run the engine: {e}")


class OptionsCandleEngine:
    def __init__(self, symphony_api, equity, series, compression_value=900):
        self.logger = CustomLogger('OptionsCandleEngine', equity)
        self.df_options_data = pd.DataFrame(columns=['Datetime', 'ExchangeInstrumentID', 'Close'])
        self.symphony_api = symphony_api
        self.df_formatted_quote = None
        self.map_strike_instrument = None
        self.compression_value = compression_value
        self.options_instruments = None
        self.equity = equity
        self.series = series
        

    async def fetch_options_ohlc(self, exchangeInstrumentID, start_time, end_time):
        try:
                response = self.symphony_api.get_ohlc(exchangeSegment='NSEFO', exchangeInstrumentID=exchangeInstrumentID, startTime=start_time, endTime=end_time, compressionValue=self.compression_value)
                return self.symphony_api.format_ohlc_options(response)
        except Exception as e:
            self.logger.log_message('error', f"Failed to fetch options ohlc for instrument {exchangeInstrumentID}: {e}")

    
    async def form_options_df(self, instruments):
        try:
            while True:
                final_options_df = pd.DataFrame(columns=['Datetime', 'ExchangeInstrumentID', 'Close'])
                current_datetime = datetime.now()
                start_time = (datetime.now().replace(hour=9, minute=15, second=0)).strftime("%b %d %Y %H%M%S")
                end_time = (datetime.now().replace(hour=16, minute=00, second=0)).strftime("%b %d %Y %H%M%S")
                for instrument in instruments:
                    response = await self.symphony_api.get_ohlc(exchangeSegment='NSEFO', exchangeInstrumentID=instrument['exchangeInstrumentID'], startTime=start_time, endTime=end_time, compressionValue=900)                 
                    # formatted_df = self.symphony_api.format_ohlc_options(response)
                    # final_options_df = pd.concat([final_options_df, formatted_df], ignore_index=True)
                    # await self.update_dataframe_options(final_options_df)
                await asyncio.sleep(constants.FETCH_INTERVAL_SECONDS)
        except Exception as e:
            self.logger.log_message('error', f"Failed to form options df: {e}")

    
    async def update_dataframe(self, df):
        try:
            self.df_options_data = df
        except Exception as e:
            self.logger.log_message('error', f"Failed to update dataframe: {e}")

    async def _form_instrument_strike_map(self, df, strike_prices):
        try:
            self.map_strike_instrument = {(strike, option_type): df.loc[(df['Strike'] == strike) & (df['OptionType'] == option_type), 'ExchangeInstrumentID'].iloc[0] for strike in strike_prices for option_type in ['CE', 'PE'] if (strike, option_type) in zip(df['Strike'], df['OptionType'])}


        except Exception as e:
            self.logger.log_message('error', f"Failed to form instrument strike map: {e}")

    async def get_options_instruments(self, spot_close_price, symbol, strike, exchangeSegment=['NSEFO']):
        try:
            # rounding off the close price to the nearest 50
            
            
            spot_close_price_rounded = round(spot_close_price/strike)*strike
            
            # make a list of 20 strike prices above and below the spot close price at interval of 50
            strike_prices = [spot_close_price_rounded + i*strike for i in range(-20, 20)]
            
            
            # get closest expiry date
            # exchangeSegment: int, series: str, symbol: str
            symphony_api = SymphonyFintechAPI(series=self.series,equity=self.equity)
            symphony_api.get_headers()
            
            closest_expiry_date = symphony_api.get_closest_expiry_date(exchangeSegment=2, series=self.series, symbol=symbol)
            
            df_formatted_masters = symphony_api.get_formatted_masters(exchangeSegment=exchangeSegment,symbol=symbol)

            # keep only where the ExpiryDate is equal to the closest expiry date
            df_formatted_masters = df_formatted_masters[df_formatted_masters['ExpiryDate'] == closest_expiry_date]
            
            # check strike data type and convert to int if necessary
            if df_formatted_masters['Strike'].dtype != 'int64':
                df_formatted_masters['Strike'] = df_formatted_masters['Strike'].astype(int)

            filtered_df = df_formatted_masters[df_formatted_masters['Strike'].isin(strike_prices)]
            
            filtered_df.reset_index(drop=True, inplace=True)

            await self._form_instrument_strike_map(filtered_df, strike_prices)
            # Construct list of dictionaries in the required format
            instruments = []
            
            for _, row in filtered_df.iterrows():
                instruments.append({
                    'exchangeSegment': int(row['InstrumentType']),  # Assuming the exchange segment is always 1
                    'exchangeInstrumentID': int(row['ExchangeInstrumentID'])
                })

            await self.update_options_instruments(instruments)
            return instruments
        except Exception as e:
            self.logger.log_message('error', f"Failed to get options instruments: {e}")

    async def get_df_options_data(self):
        return self.df_options_data

    # function to update options_instruments
    async def update_options_instruments(self, instruments):
        self.logger.log_message('info', f"Updated options instruments, {instruments}")
        self.options_instruments = instruments

    async def run(self):
        try:
            # Start fetching and inserting quotes asynchronously
            await self.form_options_df(self.options_instruments)
            # await asyncio.gather(
            #     self.fetch_quotes(instruments=options_instruments, message_code=1501)
            # )
        except Exception as e:
            self.logger.log_message('error', f"Failed to run the engine: {e}")


if __name__ == "__main__":
    # spot_candle_engine = SpotCandleEngine()
    # asyncio.run(spot_candle_engine.run(), debug=True)

    symphony_api = SymphonyFintechAPI() 
    symphony_api.get_headers()
    
    options_candle_engine = OptionsCandleEngine(symphony_api=symphony_api)
    asyncio.run(options_candle_engine.run(), debug=True)    