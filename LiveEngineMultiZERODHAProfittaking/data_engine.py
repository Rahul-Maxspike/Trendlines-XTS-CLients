# local imports
import constants
from logging_config import CustomLogger  

# library imports
import requests
import time
import json
#import asyncpg
import constants
import pandas as pd
from datetime import datetime, timezone
from io import StringIO



class SymphonyFintechAPI:
    def __init__(self, series, equity):
        self.source = constants.SOURCE
        self.base_url = constants.ROOT_URL
        self.token = None
        self.endpoints = {
            'subscribe': '/instruments/subscription',
            'quote': '/instruments/quotes',
            'masters': '/instruments/master',
            'expiry': '/instruments/instrument/expiryDate',
            'ohlc': 'instruments/ohlc'
        }
        self.headers = {
            'Content-Type': 'application/json'
        }

        # Initialize logger with filename 'dataEngine'
        self.logger = CustomLogger('dataEngine', equity)
        self.series = series


    def _make_request(self, endpoint, method='GET', data=None):
        try:
            url = self.base_url + endpoint
            headers = self.headers.copy()

            if method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError("Invalid HTTP method")
            return response
        except Exception as e:
            self.logger.log_message('error', f"Error making {method} request to {url}: {e}")

    def get_headers(self):
        # calling an api endpoint to get the headers
        enpoint = 'http://192.168.1.8:5005/headers/market'
        response = requests.get(enpoint)
        print(response.json())
        print(response.status_code)
        if response.status_code == 200:
            self.headers = response.json()
            self.logger.log_message('info', "Got headers")
        else:
            self.logger.log_message('error', "Error getting headers")
            self.logger.log_message('error', response.json())


    def subscribe(self, instruments, message_code):
        # calling the subscribe endpoint base_url/instruments/subscription
        endpoint = self.endpoints['subscribe']
        data = {
            'instruments': instruments,
            'xtsMessageCode': message_code
        }
        response = self._make_request(endpoint, method='POST', data=data)

        if response.status_code == 200:
            self.logger.log_message('info', "Subscribed to instruments")
        else:
            self.logger.log_message('error', "Error subscribing to instruments")
            self.logger.log_message('error', response.json())

    def get_ohlc(self, exchangeSegment, exchangeInstrumentID, startTime, endTime, compressionValue):
        # calling the ohlc endpoint base_url/instruments/ohlc
        endpoint = self.endpoints['ohlc']
        data = {
            'exchangeSegment': exchangeSegment,
            'exchangeInstrumentID': exchangeInstrumentID,
            'startTime': startTime,
            'endTime': endTime,
            'compressionValue': compressionValue
        }
        response = self._make_request(endpoint, method='GET', data=data)

        if response.status_code == 200:
            return response.json()
        else:
            self.logger.log_message('error', "Error getting ohlc")
            self.logger.log_message('error', response.json())

    def format_ohlc_spot(self, ohlc, drop_last=True, subtract_time=True):
        data_string = ohlc['result']['dataReponse']

        # replace ',' with '\n'
        data_string = data_string.replace(',', '\n')

        # Replace '|' with ',' to convert the string into CSV format
        data_csv = data_string.replace('|', ',')

        # Use StringIO to treat the string as a file-like object and read it as CSV
        df = pd.read_csv(StringIO(data_csv), header=None, names=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInterest', 'Ignore'])
        
        # drop the 'Volume', 'OpenInterest', 'Ignore' column
        df.drop(columns=['Volume', 'OpenInterest', 'Ignore'], inplace=True)

        # convert Timestamp to datetime object
        df['Datetime'] = pd.to_datetime(df['Datetime'], unit='s')


        if subtract_time:
            # subtract time from the Timestamp
            df['Datetime'] = df['Datetime'].apply(lambda x: x - pd.Timedelta(minutes=14, seconds=59))

        if drop_last:
            # drop the last row
            df.drop(df.tail(1).index, inplace=True)

        return df

    
    def format_ohlc_options(self, ohlc):
        data_string = ohlc['result']['dataReponse']
        
        # replace ',' with '\n'
        data_string = data_string.replace(',', '\n')

        # Replace '|' with ',' to convert the string into CSV format
        data_csv = data_string.replace('|', ',')

        # Use StringIO to treat the string as a file-like object and read it as CSV
        df = pd.read_csv(StringIO(data_csv), header=None, names=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInterest', 'Ignore'])

        # drop the 'Volume', 'OpenInterest', 'Ignore' column
        df.drop(columns=['Volume', 'OpenInterest', 'Ignore'], inplace=True)

        # convert Timestamp to datetime object
        df['Datetime'] = pd.to_datetime(df['Datetime'], unit='s')

        # subtract time from the Timestamp
        df['Datetime'] = df['Datetime'].apply(lambda x: x - pd.Timedelta(minutes=14, seconds=59))

        # drop the last row
        df.drop(df.tail(1).index, inplace=True)
        return df

    def get_quote(self, instruments, message_code, publishFormat='JSON'):
        # calling the quote endpoint base_url/instruments/quotes
        endpoint = self.endpoints['quote']
        data = {
            'instruments': instruments,
            'xtsMessageCode': message_code,
            'publishFormat': publishFormat
        }
        response = self._make_request(endpoint, method='POST', data=data)

        if response.status_code == 200:
            return response.json()
        else:
            self.logger.log_message('error', "Error getting quote")
            self.logger.log_message('error', response.json())


    def format_spot_quote(self, quote):
        # Parse the JSON response
        response_data = quote

        # Extracting quotes from the listQuotes field
        quotes = response_data['result']['listQuotes']

        # Extracting fields from the first quote (assuming only one quote is present)
        first_quote = json.loads(quotes[0])
        
        # Extracting individual fields from the quote
        last_update_time = first_quote['LastUpdateTime']
        open_price = first_quote['Open']
        high_price = first_quote['High']
        low_price = first_quote['Low']
        close_price = first_quote['Close']

        # Convert timestamp to datetime object
        datetime_object = datetime.fromtimestamp(last_update_time)

        # Format datetime object to a specific time format
        last_update_time = datetime_object.strftime('%Y-%m-%d %H:%M:%S')

        # Print the formatted quote for debugging or logging
        print(f"Time: {last_update_time}, Open: {open_price}, High: {high_price}, Low: {low_price}, Close: {close_price}")

        # Return a dictionary with extracted fields
        return {
            'time': last_update_time,
            'open_price': open_price,
            'high_price': high_price,
            'low_price': low_price,
            'close_price': close_price
        }
    
        
    # Function for Options
    def _get_masters(self, exchangeSegment: list):
        # calling the masters endpoint base_url/instruments/master
        endpoint = self.endpoints['masters']
        data = {
            'exchangeSegmentList': exchangeSegment,
        }
        response = self._make_request(endpoint, method='POST', data=data)
        print(response.status_code)

        if response.status_code == 200:
            return response.json()
        else:
            self.logger.log_message('error', f"Error getting masters: error status code{response.status_code}")
            self.logger.log_message('error', response.json())
    
    def get_formatted_masters(self,symbol:str,exchangeSegment: list):
        response = self._get_masters(exchangeSegment)
        response = response['result'].split('\n')
        
        # split at ,
        response = [x.split(',') for x in response]
        # in each sublist split at |
        response = [[y.split('|') for y in x] for x in response]
        columns = ['ExchangeSegment', 'ExchangeInstrumentID', 'InstrumentType', 'Name', 'Description', 'Series', 'NameWithSeries', 'InstrumentID', 'PriceBand.High', 'PriceBand.Low', 'FreezeQty', 'TickSize', 'LotSize', 'Multiplier', 'Ignore', 'displayName', 'ExpiryDate', 'Strike', 'OptionType', 'TickerName', 'Ignore2', 'Ignore3', 'ticker']
        df = pd.DataFrame([sublist[0] for sublist in response], columns=columns)
        # keep only where Name is 'NIFTY'
        df = df[df['Name'] == symbol]
        # keep only where Series is 'OPTIDX'
        df = df[df['Series'] == self.series]
        # reset index
        df.reset_index(drop=True, inplace=True)

        # convert 3 to CE and 4 to PE in OptionType
        df['OptionType'] = df['OptionType'].apply(lambda x: 'CE' if x == '3' else 'PE')
        # convert ExpiryDate to datetime object
        df['ExpiryDate'] = pd.to_datetime(df['ExpiryDate'])
        return df

    def get_closest_expiry_date(self, exchangeSegment: int, series: str, symbol: str):
        # calling the expiry endpoint base_url/instruments/instrument/expiryDate
        endpoint = self.endpoints['expiry']
        endpoint = f"{endpoint}?exchangeSegment={exchangeSegment}&series={series}&symbol={symbol}"
        url = self.base_url + endpoint
        response = requests.get(url, headers=self.headers)
        date_strings = response.json()['result']
        # sort the dates in ascending order

        closest_date = min((datetime.fromisoformat(date_str) for date_str in date_strings if datetime.fromisoformat(date_str) > datetime.now()))
        if response.status_code == 200:
            return closest_date
        else:
            self.logger.log_message('error', "Error getting expiry date")
            self.logger.log_message('error', response.json())
        


# Example usage
# if __name__ == '__main__':
#     symphony_api = SymphonyFintechAPI()
#     symphony_api.get_headers()
    
    #response = symphony_api.get_ohlc(exchangeSegment='NSECM', exchangeInstrumentID=0, startTime='Apr 15 2024 091500', endTime='Apr 15 2024 151500', compressionValue=900)
    #df = symphony_api.format_ohlc_spot(response)
    #print(df)
    
    # instruments = [
    #     {
    #         'exchangeSegment': 1,
    #         'exchangeInstrumentID': 26000,
    #     }
    # ]
    # symphony_api.subscribe(instruments, message_code=1501)
    # print("*"*10)
    # response = symphony_api.get_quote(instruments, message_code=1501)
    # response = symphony_api.format_quote(response)
    # print(response)

    # response = symphony_api.get_expiry_date(2, 'OPTIDX', 'NIFTY')
    # print(response)

    # df_master = symphony_api.get_formatted_masters(['NSEFO'])

    