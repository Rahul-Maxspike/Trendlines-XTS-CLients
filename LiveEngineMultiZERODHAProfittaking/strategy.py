# local imports
import constants
from logging_config import CustomLogger ,TelegramBot

# library imports
import requests
import time
import json
#import asyncpg
import constants
import pandas as pd
import numpy as np
import asyncio
import talib
from datetime import datetime, timezone, time
from zerodha_final_engine import KiteDataEngine, SpotCandleEngine, OptionsCandleEngine, MarketDataStreamer  # Replace with Zerodha API
import os

telegram_bot = TelegramBot()
class SpotBrain:
    def __init__(self,equity):
        self.logger = CustomLogger('spotBrain', equity)
        self.df = pd.DataFrame(columns=['Datetime', 'Open', 'High', 'Low', 'Close'])
        self.window = constants.WINDOW
        self.fast_factor = constants.FAST_FACTOR
        self.slow_factor = constants.SLOW_FACTOR
        self.equity = equity
    async def populate_dataframe(self, df):
        try:
            del self.df
            self.df = df
            self.df['Close'] = self.df['Close'].astype(float)
            self.df['High'] = self.df['High'].astype(float)
            self.df['Low'] = self.df['Low'].astype(float)
            self.df['Open'] = self.df['Open'].astype(float)
            # reset the index of the dataframe
            # df.reset_index(drop=True, inplace=True)
        except Exception as e:
            self.logger.log_message('error', f"Failed to populate dataframe: {e}")

    
    def _calculate_ama(self):
        try:
            close_prices = self.df['Close']
            volatility = close_prices.pct_change().rolling(window=self.window, min_periods=self.window).std()
            fast_ema = close_prices.ewm(span=self.fast_factor * self.window, adjust=False).mean()
            slow_ema = close_prices.ewm(span=self.slow_factor * self.window, adjust=False).mean()
            ama = (fast_ema + volatility * (close_prices - slow_ema)).ewm(span=self.window, adjust=False).mean()
            self.df['AMA'] = ama
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate AMA: {e}")

    def _calculate_rsi(self):
        try:
            self.df['RSI'] = talib.RSI(self.df['Close'], timeperiod=self.window)
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate RSI: {e}")


    """
    WILDERS ATR CALCULATION
    instead of using the simple moving average, we use the Wilder's Smoothing method
    
    Old CODE:
    def _calculate_atr(self):
            try:
                self.df['high-low'] = self.df['High'] - self.df['Low']
                self.df['high-close_prev'] = abs(self.df['High'] - self.df['Close'].shift(1))
                self.df['low-close_prev'] = abs(self.df['Low'] - self.df['Close'].shift(1))
                self.df['true_range'] = self.df[['high-low', 'high-close_prev', 'low-close_prev']].max(axis=1)

                # Calculate ATR
                self.df['ATR'] = self.df['true_range'].rolling(window=self.window, min_periods=1).mean()

                # Drop intermediate columns
                self.df.drop(['high-low', 'high-close_prev', 'low-close_prev', 'true_range'], axis=1, inplace=True)
            except Exception as e:
                self.logger.log_message('error', f"Failed to calculate ATR: {e}")

    NEW CODE (WILDERS ATR CALCULATION):            
    """

    def _calculate_atr(self):
        try:
            self.df['high-low'] = self.df['High'] - self.df['Low']
            self.df['high-close_prev'] = abs(self.df['High'] - self.df['Close'].shift(1))
            self.df['low-close_prev'] = abs(self.df['Low'] - self.df['Close'].shift(1))
            self.df['true_range'] = self.df[['high-low', 'high-close_prev', 'low-close_prev']].max(axis=1)
            period = 14
            self.df['ATR'] = 0.0  # Initialize ATR column
            self.df.loc[period - 1, 'ATR'] = self.df['true_range'][:period].mean()  # Initial ATR
            for i in range(period, len(self.df)):
                self.df.loc[i, 'ATR'] = (
                    (self.df.loc[i - 1, 'ATR'] * (period - 1)) + self.df.loc[i, 'true_range']
                ) / period

            # Drop intermediate columns
            self.df.drop(['high-low', 'high-close_prev', 'low-close_prev', 'true_range'], axis=1, inplace=True)
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate ATR: {e}")

   


    def _calculate_piviot_points(self, column_name=None):
        try:
            data = self.df.copy()
            length = self.window
            if column_name == 'High':
                pivot_points = pd.DataFrame(index=data.index, columns=[column_name, f'IsPivot{column_name.capitalize()}'])

                for i in range(length, len(data) - length):
                    # Check if the current point is a pivot high
                    is_pivot_point = all(data[column_name][i] > data[column_name][i - length:i]) and all(data[column_name][i] > data[column_name][i + 1:i + length + 1])
                    # is_pivot_point = all(data[column_name][i] > data[column_name][i - length:i]) 

                    # Store the values in the DataFrame
                    pivot_points.at[data.index[i], column_name] = data[column_name][i] if is_pivot_point else None

                    pivot_points.at[data.index[i], f'IsPivot{column_name.capitalize()}'] = is_pivot_point
            
            elif column_name == 'Low':
                pivot_points = pd.DataFrame(index=data.index, columns=[column_name, f'IsPivot{column_name.capitalize()}'])
                for i in range(length, len(data) - length):
                    # Check if the current point is a pivot low
                    is_pivot_point = all(data[column_name][i] < data[column_name][i - length:i]) and all(data[column_name][i] < data[column_name][i + 1:i + length + 1])
                    # is_pivot_point = all(data[column_name][i] < data[column_name][i - length:i])

                    # Store the values in the DataFrame
                    pivot_points.at[data.index[i], column_name] = data[column_name][i] if is_pivot_point else None

                    pivot_points.at[data.index[i], f'IsPivot{column_name.capitalize()}'] = is_pivot_point
            del data

            # put False in the last 14 rows, that is from length - 14 to length
            pivot_points[f'IsPivot{column_name.capitalize()}'][-length:] = False
            return pivot_points
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate Pivot Points: {e}")
            
    def _assign_piviot_values(self):
        try:
            for i in range(1, len(self.df)):
                if self.df.at[self.df.index[i], 'PH']:
                    self.df.at[self.df.index[i], 'PH_val'] = self.df.at[self.df.index[i], 'High']
                else:
                    self.df.at[self.df.index[i], 'PH_val'] = self.df.at[self.df.index[i - 1], 'PH_val']
                if self.df.at[self.df.index[i], 'PL']:
                    self.df.at[self.df.index[i], 'PL_val'] = self.df.at[self.df.index[i], 'Low']
                else:
                    self.df.at[self.df.index[i], 'PL_val'] = self.df.at[self.df.index[i - 1], 'PL_val']
        except Exception as e:
            self.logger.log_message('error', f"Failed to assign Pivot Values: {e}")

    def _calculate_slope(self):
        try:
            self.df['Slope'] = self.df['ATR']/self.window
            
            # Initialize the first values for slope_ph and slope_pl
            # self.df.at[self.df.index[0], 'slope_ph'] = self.df.at[self.df.index[0], 'Slope']
            # self.df.at[self.df.index[0], 'slope_pl'] = self.df.at[self.df.index[0], 'Slope']
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate Slope: {e}")

    def _update_slope_pivots(self):
        try:
            for i in range(1, len(self.df)):
                if self.df.at[self.df.index[i], 'PH']:
                    self.df.at[self.df.index[i], 'slope_ph'] = self.df.at[self.df.index[i], 'Slope']
                else:
                    self.df.at[self.df.index[i], 'slope_ph'] = self.df.at[self.df.index[i - 1], 'slope_ph']
                if self.df.at[self.df.index[i], 'PL']:
                    self.df.at[self.df.index[i], 'slope_pl'] = self.df.at[self.df.index[i], 'Slope']
                else:
                    self.df.at[self.df.index[i], 'slope_pl'] = self.df.at[self.df.index[i - 1], 'slope_pl']
        except Exception as e:
            self.logger.log_message('error', f"Failed to update Slope Pivots: {e}")

    def _calcualte_upper_lower_band(self):
        try:
            self.df['upper'] = 0.0
            self.df['lower'] = 0.0

            for i in range(1, len(self.df)):
                if self.df.at[self.df.index[i], 'PH'] == True:
                    self.df.at[self.df.index[i], 'upper'] = self.df.at[self.df.index[i], 'High']
                else:
                    self.df.at[self.df.index[i], 'upper'] = (self.df.at[self.df.index[i - 1], 'upper'] - self.df.at[self.df.index[i], 'slope_ph'])


            for i in range(1, len(self.df)):
                if self.df.at[self.df.index[i], 'PL'] == True:
                    self.df.at[self.df.index[i], 'lower'] = self.df.at[self.df.index[i], 'Low']
                else:
                    self.df.at[self.df.index[i], 'lower'] = (self.df.at[self.df.index[i - 1], 'lower'] + self.df.at[self.df.index[i], 'slope_pl'])


        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate Upper and Lower Bands: {e}")

    def _calculate_upos_dnos(self):
        try:
            self.df['upos'] = 0
            self.df['dnos'] = 0

            # Calculate upos
            for i in range(1, len(self.df)):
                if self.df.at[self.df.index[i], 'PH'] != True or self.df.at[self.df.index[i], 'PL'] =='':
                    # upper_limit = self.df.at[self.df.index[i - 1], 'upper'] #Previous candle call
                    upper_limit = self.df.at[self.df.index[i], 'upper'] #Current candle call
                    if self.df.at[self.df.index[i], 'Close'] > upper_limit:
                        self.df.at[self.df.index[i], 'upos'] = 1

            # Calculate dnos
            for i in range(1, len(self.df)):
                if self.df.at[self.df.index[i], 'PL'] != True or self.df.at[self.df.index[i], 'PH'] == '':
                    # lower_limit = self.df.at[self.df.index[i - 1], 'lower'] #Previous candle call
                    lower_limit = self.df.at[self.df.index[i], 'lower'] #Current candle call
                    if self.df.at[self.df.index[i], 'Close'] < lower_limit:
                        self.df.at[self.df.index[i], 'dnos'] = 1
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate Upos and Dnos: {e}")
            
    def _calculate_signals(self):
        try:
            self.df['signal'] = 'Hold'
            buy_condition = (self.df['upos'] > self.df['upos'].shift(1)) & (self.df['signal'] != 'Buy')
            sell_condition = (self.df['dnos'] > self.df['dnos'].shift(1)) & (self.df['signal'] != 'Sell')

            self.df.loc[buy_condition, 'signal'] = 'Buy'
            self.df.loc[sell_condition, 'signal'] = 'Sell'

            
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate Signals: {e}")

    async def get_df(self):
        return self.df

    async def run(self):
        try:
            self._calculate_ama()
            self._calculate_rsi()
            self._calculate_atr()
            self.df['PH'] = self._calculate_piviot_points(column_name='High')['IsPivotHigh']
            self.df['PL'] = self._calculate_piviot_points(column_name='Low')['IsPivotLow']
            self._assign_piviot_values()
            self._calculate_slope()
            self._update_slope_pivots()
            self._calcualte_upper_lower_band()
            self._calculate_upos_dnos()
            self._calculate_signals()

            # self.df.to_csv('spot_brain.csv')
        except Exception as e:
            self.logger.log_message('error', f"Failed to calculate Pivot Points: {e}")


class OptionsBrain:
    def __init__(self, equity, strike, closest_expiry_date):
        self.equity = equity
        self.strike = strike
        self.closest_expiry_date = closest_expiry_date
        self.logger = CustomLogger('optionsBrain', equity)
        # create empty df with no columns
        self.options_df = pd.DataFrame()
        self.map_strike_instrument = None
        self.wings = self.get_wings()
        self.buy_var = 0
        self.sell_var = 0
        

    def get_wings(self):
    # if day difference is 0 then wings is 100,
    # if day difference is 1 then wings is 200, if day difference is 2 then wings is 300
    # if day difference is 3 then wings is 400, if day difference is 4 then wings is 400
    # if day difference is 5 then wings is 400, if day difference is 6 then wings is 400
        day_today = datetime.today().weekday()
        day_closest_expiry = self.closest_expiry_date.weekday()
        day_diff = day_closest_expiry - day_today
        if day_diff < 0:
            day_diff = 7 + day_diff

        wings_values = {
        0: 100,
        1: 200,
        2: 300,
        3: 400,
        4: 400,
        5: 400,
        6: 400
        }

        # Default to 400 if day_difference is greater than 6
        return wings_values.get(day_diff, 400)
    
    async def populate_dataframe(self, df):
        try:
            del self.options_df
            self.options_df = df
        except Exception as e:
            self.logger.log_message('error', f"Failed to populate dataframe: {e}")
    
    async def populate_map_strike_instrument(self, map):
        try:
            self.map_strike_instrument = map
            
            print(f'Populating map strike instrument is:{self.map_strike_instrument}')

        except Exception as e:
            
            self.logger.log_message('error', f"Failed to populate map_strike_instrument: {e}")

    async def get_df(self):
        return self.options_df
    
    def _round_to_nearest_50(self, number):
        return round(number / self.strike) * self.strike
    
    def _get_daily_diff(self, current_datetime):
        day_of_week = current_datetime.weekday()
        # Define a dictionary to map each day to its corresponding difference
        day_diff_mapping = {
            "Monday": self.wings,
            "Tuesday": self.wings,
            "Wednesday": self.wings,
            "Thursday": self.wings,
            "Friday": self.wings,
            "Saturday": self.wings,
            "Sunday": self.wings
        }
        # Return the difference based on the day of the week
        return day_diff_mapping[datetime.strftime(current_datetime, '%A')]

        
    def get_close_price_dict(self, atmSP, wingCall, wingPut, current_datetime_str_short, expiry):
        pass

    async def mark_trades(self):
        try:
            if self.options_df.isna().any().any():
                # self.logger("error","NaN values detected in options DataFrame.")
                print("NaN values detected in options DataFrame.")
                
                # Fill NaN values with 0, or any other default you need
                self.options_df.fillna(0, inplace=True)

            df = self.options_df
            position = "squareoff"

            # set the initial capital and the current capital
            capital = 100000

            first_run = True

            for i, row in enumerate(df.itertuples()):
                # timer_start = tm.time()
                # Check if this a new day and time is 09:30:00+05:30

                current_datetime_str = str(row.Datetime)
                current_datetime_str_short = current_datetime_str[:-6]

                has_traded_today = False
                has_squareoff_today = False

                # check if the time is 09:30:00+05:30 or it is the first run
                if '09:30:00' in current_datetime_str or first_run:
                    # Calculate the ATM strike price
                    atmSP = self._round_to_nearest_50(row.Close)
                    wingPut = atmSP - self._get_daily_diff(row.Datetime)
                    wingCall = atmSP + self._get_daily_diff(row.Datetime)
                    
                    # # marking the postion as 0 updating tickers_dict
                    # close_price_dict = get_close_price_dict(atmSP, wingCall, wingPut, current_datetime_str_short, row.closest_expiry)

                    # df.loc[i, ['atmSP', 'wingCall', 'wingPut', 'legPriceOrignal1', 'legPriceOrignal2', 'legPriceOrignal3', 'legPriceOrignal4']] = [atmSP, wingCall, wingPut, close_price_dict['atmSPCall'], close_price_dict['atmSPPut'], close_price_dict['wingCallPrice'], close_price_dict['wingPutPrice']]
                    if first_run:
                        # Reset values to 0 for the specified columns at row i
                        # df.loc[i, columns_to_reset] = 0
                        df.at[i, 'position'] = 'hold'
                        position = 'hold'
                        df.at[i, 'balance'] = capital
                        first_run = False
                    else:
                        df.at[i, 'position'] = 'beginx'
                        position = 'hold'
                        df.loc[i, ['atmSP', 'wingCall', 'wingPut'] ] = [atmSP, wingCall, wingPut]
                        # calculate_m2m_new(i, start_day=True, caller='beginx 9:30')
                    # sell atmSP call -> api call # sell atmSp put -> api call # buy wingPut -> api call # buy wingCall -> api call
                    
                
                # if time is 15:15:00+05:30 then squareoff all positions
                elif row.Datetime.time() == time(15, 00):
                    # buy atmSp call -> api call # buy atmSp put -> api call # sell wingPut -> api call # sell wingCall -> api call
                    capital = df.at[i-1, 'balance']
                    df.at[i, 'balance'] = df.at[i-1, 'balance']
                    df.at[i, 'position'] = position = 'squareoff'
                    df.loc[i, ['atmSP', 'wingCall', 'wingPut'] ] = [atmSP, wingCall, wingPut]
                    # store the values in the dataframe
                    # close_price_dict = get_close_price_dict(atmSP, wingCall, wingPut, current_datetime_str_short, row.closest_expiry)  
                    # df.loc[i, ['atmSP', 'wingCall', 'wingPut', 'legPriceOrignal1', 'legPriceOrignal2', 'legPriceOrignal3', 'legPriceOrignal4']] = [atmSP, wingCall, wingPut, close_price_dict['atmSPCall'], close_price_dict['atmSPPut'], close_price_dict['wingCallPrice'], close_price_dict['wingPutPrice']]         
                    # rolling_dict = calculate_m2m_new(i, caller='15:15')
                
                elif row.Datetime.time() == time(15, 30):
                    # store the values in the dataframe
                    df.loc[i, ['atmSP', 'wingCall', 'wingPut'] ] = [atmSP, wingCall, wingPut]
                    df.at[df.index[i], 'position'] = 'hold'
                    df.at[i, 'balance'] = df.at[i-1, 'balance']

                    position = 'hold'
                    
                elif row.Datetime.time() == time(9, 15):
                    # this is for time between 15:15:00+05:30 and 09:30:00+05:30
                    # store the values in the dataframe

                    df.loc[i, ['atmSP', 'wingCall', 'wingPut'] ] = [atmSP, wingCall, wingPut]
                    df.at[df.index[i], 'position'] = 'hold'
                    df.at[i, 'balance'] = df.at[i-1, 'balance']
                    position = 'hold'
                
                elif df.at[i-1, 'position'] == 'squareoff' and row.Datetime.time() > time(9, 30) and row.Datetime.time() < time(15, 15):
                    # if previous was squareoff then take position this time
                    atmSP = self._round_to_nearest_50(row.Close)
                    wingPut = atmSP - self._get_daily_diff(row.Datetime)
                    wingCall = atmSP + self._get_daily_diff(row.Datetime)
                    # close_price_dict = get_close_price_dict(atmSP, wingCall, wingPut, current_datetime_str_short, row.closest_expiry)  
                    df.at[i, 'position'] = 'beginx'
                    position = 'hold'
                    df.loc[i, ['atmSP', 'wingCall', 'wingPut']] = [atmSP, wingCall, wingPut]
                    # calculate_m2m_new(i, start_day=True, caller='beginx')
                
                else:
                    # close_price_dict = get_close_price_dict(atmSP, wingCall, wingPut, current_datetime_str_short, row.closest_expiry) 
                    if position == 'hold':
                        if row.signal == 'Buy':
                            if row.RSI < 70 and row.AMA < row.Close:
                                # buy atmSp call -> api call # Sell atmSp put -> api call # buy wingCall -> api call # buy wingPut -> api call
                                df.at[i, 'position'] = position = 'buy'                                
                                has_traded_today = True
                        
                        elif row.signal == 'Sell':
                            if row.RSI > 30 and row.AMA > row.Close:
                                # sell atmSp call -> api call # buy atmSp put -> api call # Buy wingPut -> api call # Buy wingCall -> api call
                                df.at[i, 'position'] = position = 'sell'
                                has_traded_today = True

                    elif position == 'buy':
                        if row.signal == 'Hold':
                            if row.RSI > 70:
                                # buy atmSp put -> api call x 2 # sell wingPut -> api call x 2 # sell wingCall -> api call x 2
                                df.at[i, 'position'] = position = 'squareoff'
                                has_traded_today = True
                        
                        elif row.signal == 'Sell':          
                            # buy atmSp put -> api call # sell wingPut -> api call # sell wingCall -> api call
                            df.at[i, 'position'] = position =  'squareoff'
                            has_traded_today = True

                    elif position == 'sell':
                        if row.signal == 'Hold':
                            if row.RSI < 30:              
                                # buy atmSp call -> api call # sell wingPut -> api call # sell wingCall -> api call  
                                df.at[i, 'position'] = position = 'squareoff'
                                has_traded_today = True

                                
                        elif row.signal == 'Buy':
                            df.at[df.index[i], 'position'] = position = 'squareoff'
                            has_traded_today = True
                            

                    df.at[i, 'position'] = position
                    # df.loc[i, ['atmSP', 'wingCall', 'wingPut', 'legPriceOrignal1', 'legPriceOrignal2', 'legPriceOrignal3', 'legPriceOrignal4']] = [atmSP, wingCall, wingPut, close_price_dict['atmSPCall'], close_price_dict['atmSPPut'], close_price_dict['wingCallPrice'], close_price_dict['wingPutPrice']]
                    df.loc[i, ['atmSP', 'wingCall', 'wingPut'] ] = [atmSP, wingCall, wingPut]

                    if not has_traded_today:
                        df.at[i, 'position'] = df.at[i-1, 'position']

                    
                    # called everytime
                    # calculate_m2m_new(i, caller='daily')

                    # if df.at[i, 'totalPL'] < -3300:
                    #     # squareoff all positions
                    #     # df.loc[i, columns_to_reset] = 0
                    #     df.at[i, 'position'] = position = 'squareoff'
                    #     # calculate_m2m_new(i, caller='stoploss')
                    #     # df.at[i, 'totalPL'] = -3300
                    #     # df.at[i, 'balance'] = df.at[i-1, 'balance'] - 3300
                        

                    
                
                # timer_end = tm.time()
                # logging.info(f"Time taken for this iteration: {timer_end - timer_start} seconds")


                # df.at[df.index[i], 'position'] = position
            
            self.options_df = df
            # df.to_csv('options_brain.csv')
        except Exception as e:
            self.logger.log_message('error', f"Failed to mark trades: {e}")

    async def put_instruments(self):
        try:
            # get matching strike for the given atmSP, wingCall, wingPut and store in df
            df = self.options_df
            

            # Map prices to instrument IDs and create new columns
            # Perform the mapping from strike prices to instrument IDs
            df['atmce'] = df['atmSP'].map(lambda x: int(self.map_strike_instrument.get((x, 'CE'), 0)))
            df['atmpe'] = df['atmSP'].map(lambda x: int(self.map_strike_instrument.get((x, 'PE'), 0)))
            df['wce'] = df['wingCall'].map(lambda x: int(self.map_strike_instrument.get((x, 'CE'),0)))
            df['wpe'] = df['wingPut'].map(lambda x: int(self.map_strike_instrument.get((x, 'PE'), 0)))


            # Set the updated DataFrame
            self.options_df = df
        except Exception as e:
            self.logger.log_message('error', f"Failed to put instruments: {e}")
        
    
    async def write_options_brain(self):
        # try:
        #     # Write the updated DataFrame to a CSV
        #     self.options_df.to_csv(f'equities/{self.equity}_options_brain.csv')
        # except Exception as e: 52568,52570,52573,52551
        #     self.logger.log_message('error', f"Failed to write OptionsBrain: {e}")
        try:
        # Loop over clientcodes and write the updated DataFrame for each client
            file_path = f'equities/{self.equity}_options_brain.csv'
            # self.options_df.loc[self.options_df.index[-1], 'atmSP'] = 23300
            # self.options_df.loc[self.options_df.index[-1], 'wingCall'] = 23400
            # self.options_df.loc[self.options_df.index[-1], 'wingPut'] = 23200
            # self.options_df.loc[self.options_df.index[-1], 'atmce'] = 52568
            # self.options_df.loc[self.options_df.index[-1], 'atmpe'] = 52570
            # self.options_df.loc[self.options_df.index[-1], 'wce'] = 52573
            # self.options_df.loc[self.options_df.index[-1], 'wpe'] = 52551
            # self.options_df.loc[self.options_df.index[-1], 'position'] = 'beginx'

            if self.options_df.loc[self.options_df.index[-1], 'position'] == 'buy' and self.buy_var==0:
                telegram_bot.send_message(f"NIFTY BUY CAME")
                self.buy_var = 1
            elif self.options_df.loc[self.options_df.index[-1], 'position'] == 'sell' and self.sell_var==0:
                telegram_bot.send_message(f"NIFTY SELL CAME")
                self.sell_var = 1
                

            self.options_df.to_csv(file_path)
        except Exception as e:
            self.logger.log_message('error', f"Failed to write OptionsBrain: {e}")

    async def run(self):
        try:
            await self.mark_trades()
            await self.put_instruments()
            await self.write_options_brain()
            # # change last row postion to squareoff
            # self.options_df.at[self.options_df.index[-1], 'position'] = 'squareoff'
            
            return self.options_df
        except Exception as e:
            self.logger.log_message('error', f"Failed to run OptionsBrain: {e}")



class CMPPutter:
    def __init__(self, kite, equity, options_candle_engine):
        self.logger = CustomLogger('CMPPutter', equity)
        # create empty df with no columns
        self.options_df = pd.DataFrame()
        self.options_candle_engine = options_candle_engine
        self.leg_prices = 0
        self.equity = equity
        self.instrument_ids = []

    async def populate_dataframe(self, df):
        # self.options_df = pd.read_csv(f'equities/{self.equity}_options_brain.csv')
        self.options_df = df.iloc[-1]
        
        self.instrument_ids = [self.options_df['atmce'], self.options_df['atmpe'], self.options_df['wce'], self.options_df['wpe']]
    
    async def get_current_price(self):
        try:
            # Get current prices for all instruments in one go
            self.leg_prices = {
                self.instrument_ids[0]: await self.options_candle_engine.get_current_market_price(self.instrument_ids[0]),
                self.instrument_ids[1]: await self.options_candle_engine.get_current_market_price(self.instrument_ids[1]),
                self.instrument_ids[2]: await self.options_candle_engine.get_current_market_price(self.instrument_ids[2]),
                self.instrument_ids[3]: await self.options_candle_engine.get_current_market_price(self.instrument_ids[3]),
            }
            
            
            
            # self.instrument_ids = [self.options_df['atmce'], self.options_df['atmpe'], self.options_df['wce'], self.options_df['wpe']]

            return self.leg_prices


        except Exception as e:
            self.logger.log_message('error', f"Failed to get current price: {e}, when equity is {self.equity}\n")

    # def get_tradesheet_path(self, equity):
    #     # tradesheet paths have a cycle number appended to them
    #     # check till 3 cycles and return the highest cycle number that exists
    #     # f'Tradesheets/{self.equity}_trade_sheet_cycle1.csv'
    #     for i in range(1, 10):
    #         if not os.path.exists(f'Tradesheets/{equity}_trade_sheet_cycle{i}.csv'):
    #             return f'Tradesheets/{equity}_trade_sheet_cycle{i-1}.csv'

    # async def write_to_csv(self):
    #         try:
    #             # Writing leg prices to DataFrame
    #             equities = [self.equity, f"{self.equity}15"]
    #             for equity in equities:
    #                 df = pd.DataFrame(self.leg_prices, index=[0])
                    
    #                 trade_sheet_path = self.get_tradesheet_path(equity)
    #                 # Read the existing trade sheet
    #                 trade_sheet = pd.read_csv(trade_sheet_path)
    #                 trade_sheet = trade_sheet.copy()  # Ensure working with a copy


                    
                    
    #                 # Update the CMP column in the trade_sheet
    #                 for i in range(4):
    #                     instrument_id = self.instrument_ids[i]
    #                     leg_price = df.at[0, f'legPriceOg{i}']
                        
    #                     if instrument_id in trade_sheet['InstrumentID'].values:
    #                         # Update the CMP for rows where InstrumentID matches
    #                         trade_sheet.loc[trade_sheet['InstrumentID'] == instrument_id, 'CMP'] = leg_price
    #                     else:
    #                         # Create a new row with default values and the specific InstrumentID and CMP
    #                         new_row = pd.DataFrame([{col: 0 for col in trade_sheet.columns}])
    #                         new_row['InstrumentID'] = instrument_id
    #                         new_row['CMP'] = leg_price
    #                         trade_sheet = pd.concat([trade_sheet, new_row], ignore_index=True)
                        

    #                 # Write the updated trade sheet back to the CSV
    #                 trade_sheet.to_csv(trade_sheet_path, index=False)
    #         except Exception as e:
    #             self.logger.log_message('error', f"Failed to write to csv: {e}")



    # async def run(self):
    #     try:
    #         # await self.populate_dataframe()
    #         await self.get_current_price()
    #         # await self.write_to_csv()
    #     except Exception as e:
    #         self.logger.log_message('error', f"Failed to run CMPPutter from run: {e}")

