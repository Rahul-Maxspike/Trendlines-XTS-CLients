# Library Imports
import constants
import time
import pandas as pd
import requests
import json
from datetime import datetime
import os
import tempfile
import numpy as np
import asyncio
import httpx
from termcolor import colored
from typing import List 

# Local Imports
from logging_config import CustomLogger, TelegramBot
from file_engine import FileResetter, FileCreator


class SymphonyInteractiveAPI:
    def __init__(self, base_qty, equity, freeze_qty, offset=0):
        self.logger = CustomLogger(filename="SymphonyInteractiveAPI", equity =equity)
        self.__equity = equity
        self.daily_json_path = f'daily_jsons/{self.__equity}.json'
        self.file_creator = FileCreator(equity)
        self.__multiplier = 0
        self.__base_quantity = base_qty
        self.__quantity = 0
        self.offset = offset
        self.cycle_count = self.get_cycle_count()
        self.active_instruments = {}
        self.trade_sheet = self.read_trade_sheet()
        self.telegramBot = TelegramBot()
        self.endpoints = {
            "strategy_funds": (f"{constants.CLIENT_MASTER['uri']}/get_client_strategy_funds?ClientId={{client_id}}&StrategyId={{strategy_id}}", "GET"),
            "place_order": (constants.OMS_URI, "POST"),
            "order_status": (f"{constants.OMS_URI}{{orderId}}", "GET"),
        }
        self.stoploss_time = time.localtime()
        if self.__equity != 'NIFTY1':
            minute = (self.stoploss_time.tm_min // 15) * 15
            self.stoploss_time = time.struct_time((self.stoploss_time.tm_year, self.stoploss_time.tm_mon, self.stoploss_time.tm_mday, self.stoploss_time.tm_hour, minute, 0, self.stoploss_time.tm_wday, self.stoploss_time.tm_yday, self.stoploss_time.tm_isdst))
            
    
    def _make_request(self, endpoint, data=None):
        try:
            url = endpoint[0]
            method = endpoint[1]
            if method == "POST":
                response = requests.post(url, json=data)
            elif method == "GET":
                response = requests.get(url)
            elif method == "PUT":
                response = requests.put(url, json=data)
            elif method == "DELETE":
                response = requests.delete(url, json=data)
            else:
                raise ValueError("Invalid HTTP method")
            return response
        except Exception as e:
            self.logger.log_message(
                "error", f"Error making request to: {e}"
            )
    
    def read_trade_sheet(self):
        try:
            return pd.read_csv(f"Tradesheets/{self.__equity}_trade_sheet_cycle{self.cycle_count}.csv")
        except Exception as e:
            self.logger.log_message("error", f"Error in read_trade_sheet: {e}")

    def write_trade_sheet(self, data):
        try:
            data.to_csv(f"Tradesheets/{self.__equity}_trade_sheet_cycle{self.cycle_count}.csv", index=False)
        except Exception as e:
            self.logger.log_message("error", f"Error in write_trade_sheet: {e}")

    
    async def update_trade_sheet(self, order_response):
        try:
            pass
        except Exception as e:
            self.logger.log_message("error", f"Error in update_trade_sheet: {e}")

    async def get_order_status(self, order_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.endpoints['order_status'][0].format(orderId=order_id))
            status_data = response.json()
            return status_data

    async def pull_order_status(self, order_id: str):
        """Keep pulling the order status until it reaches the target status."""
        print(colored(f"Getting status for order {order_id}", "yellow"))
        target_status = ["filled", "rejected"]
        while True:
            status_data = await self.get_order_status(order_id)
            status = status_data.get("status")

            # Break if the target status is reached
            if status in target_status:
                print(colored(f"Order {order_id} reached status: {status}, Price = {status_data['placedPrice']}, Quantity = {status_data['placedQuantity']}", "green"))
                return status_data

            # Wait for a few seconds before polling again
            await asyncio.sleep(3)

    def get_total_funds(self):
        try:
            # make the api call to get the funds

            url = self.endpoints["strategy_funds"][0].format(client_id=constants.CLIENT_MASTER["clientId"], strategy_id=constants.CLIENT_MASTER["strategyId"])
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if self.__equity == 'NIFTY1':
                    return 150000
                elif self.__equity == 'NIFTY15': 
                    return 150000
                else:
                    return 0  
        except Exception as e:
            self.logger.log_message("error", f"Error in get_funds: {e}")

    def set_multiplier(self):
        try:
            # available_funds = self.get_available_funds()
            available_funds = self.get_total_funds()
            self.__multiplier = int(available_funds / 150000)
        except Exception as e:
            self.logger.log_message("error", f"Error in get_multiplier: {e}")

    def read_daily_json(self):
        try:
            with open(self.daily_json_path, "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            self.logger.log_message("error", f"Error in read_daily_json: {e}")
        
    def convert_to_serializable(self, data):
        if isinstance(data, dict):
            return {key: self.convert_to_serializable(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.convert_to_serializable(item) for item in data]
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        else:
            return data

    def write_daily_json(self, data):
        try:
            # Convert data to a JSON serializable format
            serializable_data = self.convert_to_serializable(data)
            # Get the directory of the destination file
            destination_dir = os.path.dirname(self.daily_json_path)
            # Write to a temporary file first
            try:
                fd, temp_file = tempfile.mkstemp(dir=destination_dir)
                with os.fdopen(fd, 'w') as f:
                    json.dump(serializable_data, f)
                os.replace(temp_file, self.daily_json_path)
            except Exception as e:
                self.logger.log_message("error", f"Error writing to temporary file: {e}")
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
        except Exception as e:
            self.logger.log_message("error", f"Error in write_daily_json: {e}")

    def get_cycle_count(self):
        try:
            return self.read_daily_json()["Cycle Count"]
        except Exception as e:
            self.logger.log_message("error", f"Error in get_cycle_count: {e}")

    def write_cycle_count(self, cycle_count):
        try:
            response = self.read_daily_json()
            response["Cycle Count"] = cycle_count
            self.write_daily_json(response)
        except Exception as e:
            self.logger.log_message("error", f"Error in write_cycle_count: {e}")


    def check_and_update_highest_m2m(self, m2m):
        try:
            daily_json = self.read_daily_json()
            highest_m2m = daily_json["highest_m2m"]
            if m2m > highest_m2m:
                daily_json["highest_m2m"] = m2m
                self.write_daily_json(daily_json)
                return True
            else:
                return False
        except Exception as e:
            self.logger.log_message("error", f"Error in check_and_update_highest_m2m: {e}")

    
    def verify_positions(self, trade_sheet, placed_instruments, position):
        
        positions = {'beginx': [-1, -1, 1, 1], 'buy': [0, -2, 2, 2], 'sell': [-2, 0, 2, 2], 'squareoff': [0, 0, 0, 0], 'hold': [0, 0, 0, 0]}
        expected_positions = positions[position]

        # get absolute max of expected positions
        max_leg_position = max([abs(pos) for pos in expected_positions])
        # Ensure max_position is not zero to avoid division by zero
        if max_leg_position == 0 and position != "squareoff":
            return False

        # Filter out NaN values from NetQuantity
        if trade_sheet['NetQuantity'].notna().any():
            max_net_quantity = trade_sheet['NetQuantity'].abs().max()
        else:
            raise ValueError("NetQuantity column contains only NaN values.")
        

        # Now calculate the lot size
        if max_leg_position == 0:
            absolute_leg_quantity = 0
        else:
            absolute_leg_quantity = max_net_quantity / max_leg_position
        
        for idx, (key, instrument_id) in enumerate(placed_instruments.items()):
            # Find the corresponding row in the trade sheet
            instrument_row = trade_sheet[trade_sheet['InstrumentID'] == instrument_id]
            
            if not instrument_row.empty:
                if instrument_row['CMP'].values[0] == 0:
                    return False
                # Get the Quantity from the row (NetQuantity renamed to Quantity)
                quantity = instrument_row['NetQuantity'].values[0]
                
                # Calculate the position based on Quantity and lot size
                if absolute_leg_quantity == 0:
                    actual_position = 0
                else:
                    actual_position = (quantity / absolute_leg_quantity)

                # Compare the actual position with the expected position
                if (actual_position != expected_positions[idx]) or (instrument_row['LegPosition'].values[0] != expected_positions[idx]):
                    return False
            else:
                # If no matching instrument is found in the trade sheet
                return False
        # All positions match
        return True

    def put_cmp(self, cmp: dict):
        trade_sheet = self.read_trade_sheet()
        # loop through the cmp dictionary
        for instrument_id, leg_price in cmp.items():
            if instrument_id in trade_sheet['InstrumentID'].values:
                # Update the CMP for rows where InstrumentID matches
                trade_sheet.loc[trade_sheet['InstrumentID'] == instrument_id, 'CMP'] = leg_price
            else:
                # Create a new row with default values and the specific InstrumentID and CMP
                new_row = pd.DataFrame([{col: 0 for col in trade_sheet.columns}])
                new_row['InstrumentID'] = instrument_id
                new_row['CMP'] = leg_price
                trade_sheet = pd.concat([trade_sheet, new_row], ignore_index=True)
        # Write the updated trade sheet
        self.write_trade_sheet(trade_sheet)

    def calculate_m2m(self, position):
        try:
            trade_sheet = self.read_trade_sheet()
            daily_json = self.read_daily_json()
            # only keep the placed instruments
            trade_sheet = trade_sheet[trade_sheet['InstrumentID'].isin(self.active_instruments.values())]
            # check if trade_sheet has 4 rows
            if trade_sheet.shape[0] < 4:
                self.logger.log_message("error", "Trade sheet does not have 4 rows")
                return daily_json['Current M2M']
            
            is_trade_sheet_correct = self.verify_positions(trade_sheet, self.active_instruments, position)
            if not is_trade_sheet_correct:
                self.logger.log_message("error", f"Trade sheet is incorrect, expected position {position}")
                # return prevous m2m from daily_json
                return daily_json['Current M2M']
            
            
            
            def calculate_realised_m2m(row):
                if row['NetQuantity'] > 0:
                    return (row['SellAveragePrice'] * row['SellQuantity']) - (row['BuyAveragePrice'] * (row['BuyQuantity'] - row['NetQuantity']))
                elif row['NetQuantity'] < 0:
                    return (row['SellAveragePrice'] * (row['SellQuantity'] - abs(row['NetQuantity']))) - (row['BuyAveragePrice'] * row['BuyQuantity'])
                elif row['NetQuantity'] == 0:
                    return (row['SellAveragePrice'] * row['SellQuantity']) - (row['BuyAveragePrice'] * row['BuyQuantity'])
                else:
                    self.logger.log_message("error", "Error in calculate_realised_m2m")
                    return False

            def calculate_unrealised_m2m(row):
                try:
                    net_quantity = row['NetQuantity']
                    if net_quantity == 0:
                        return 0
                    elif net_quantity > 0:
                        return abs(net_quantity) * (row['CMP'] - row['BuyAveragePrice'])
                    elif net_quantity < 0:
                        return abs(net_quantity) * (row['SellAveragePrice'] - row['CMP'])
                    else:
                        self.logger.log_message("error", "Error in calculate_unrealised_m2m")
                        return False
                except Exception as e:
                    self.logger.log_message("error", f"Error in calculate_unrealised_m2m: {e}")
                    print(e)

            trade_sheet['RealisedM2M'] = trade_sheet.apply(calculate_realised_m2m, axis=1)
            trade_sheet['UnrealisedM2M'] = trade_sheet.apply(calculate_unrealised_m2m, axis=1)
            trade_sheet['M2M'] = trade_sheet['RealisedM2M'] + trade_sheet['UnrealisedM2M']

            self.trade_sheet = trade_sheet
            self.write_trade_sheet(trade_sheet)

            daily_json['Realised M2M'] = trade_sheet['RealisedM2M'].sum()
            daily_json['Unrealised M2M'] = trade_sheet['UnrealisedM2M'].sum()
            daily_json['Current M2M'] = trade_sheet['M2M'].sum()

            self.write_daily_json(daily_json)

            
            
            return daily_json['Current M2M']
        except Exception as e:
            self.logger.log_message("error", f"Error in calculate_m2m: {e}")

    # def check_stoploss(self, position, placed_instruments, cmp_dict):
    #     try:
    #         self.put_cmp(cmp_dict)
    #         self.active_instruments = placed_instruments
    #         current_m2m = self.calculate_m2m(position)
    #         self.check_and_update_highest_m2m(current_m2m)
    #         highest_m2m = self.read_daily_json()["highest_m2m"]
    #         if position == "beginx":
    #             stoploss_price = highest_m2m - (self.get_total_funds()*0.015)
    #         else:
    #             stoploss_price = highest_m2m - (self.get_total_funds()*0.03)
    #         print(f"{self.__equity} Current M2M: {current_m2m}, Stoploss at: {stoploss_price}")
    #         data = self.read_daily_json()
    #         data['Stoploss Price'] = stoploss_price
    #         data['Position'] = position
    #         self.write_daily_json(data)
    #         # Add one minute to stoploss_time
    #         if self.__equity == 'NIFTY1':
    #             new_stoploss_minute = (self.stoploss_time.tm_min + 1) % 60
            
    #         elif self.__equity == 'NIFTY15':
    #             new_stoploss_minute = (self.stoploss_time.tm_min + 15) % 60
    #         else:
    #             new_stoploss_minute = (self.stoploss_time.tm_min + 15) % 60

    #         if new_stoploss_minute == time.localtime().tm_min:
    #             self.stoploss_time = time.localtime()
    #             if current_m2m < stoploss_price:
    #                 return True
    #             else:
    #                 return False
    #     except Exception as e:
    #         self.logger.log_message("error", f"Error in check_stoploss: {e}")

    def check_stoploss(self, position, placed_instruments, cmp_dict):
        try:
            if self.__equity == 'NIFTY1':
                new_stoploss_minute = (self.stoploss_time.tm_min + 1) % 60
            
            elif self.__equity == 'NIFTY15':
                new_stoploss_minute = (self.stoploss_time.tm_min + 15) % 60
            else:
                new_stoploss_minute = (self.stoploss_time.tm_min + 15) % 60
            self.put_cmp(cmp_dict)
            self.active_instruments = placed_instruments
            data = self.read_daily_json()
            current_m2m = self.calculate_m2m(position)

            data['Current M2M'] = current_m2m
            data['Position'] = position
            self.write_daily_json(data)
            #tick level stoploss 

            if position == "beginx":
                target_price = self.get_total_funds()*0.009
            else:
                target_price = self.get_total_funds()*0.04
            if current_m2m > target_price:
                print("Target price reached")
                return True
                    
            # print(f"Stoploss Time: {self.stoploss_time.tm_min}, Current Time: {time.localtime().tm_min}")
            if new_stoploss_minute == time.localtime().tm_min:
                print("Stoploss Change time reached")
                self.put_cmp(cmp_dict)
                self.active_instruments = placed_instruments
                current_m2m = self.calculate_m2m(position)
                self.check_and_update_highest_m2m(current_m2m)
                highest_m2m = self.read_daily_json()["highest_m2m"]
                if position == "beginx":
                    stoploss_price = highest_m2m - (self.get_total_funds()*0.015)
                    target_price = self.get_total_funds()*0.009
                else:
                    stoploss_price = highest_m2m - (self.get_total_funds()*0.03)
                    target_price = self.get_total_funds()*0.04
                print(f"{self.__equity} Current M2M: {current_m2m}, Stoploss at: {stoploss_price} , Target at: {target_price}")
                data = self.read_daily_json()
                data['Stoploss Price'] = stoploss_price
                data['Position'] = position
                self.write_daily_json(data)
                self.stoploss_time = time.localtime()
                if current_m2m < stoploss_price or current_m2m > target_price:
                    return True
                else:
                    return False
            
            # print(colored(f"{self.__equity} Current M2M: {round(current_m2m, 2)}, Stoploss Price: {round(stoploss_price, 2)},Target Profit: {round(target_profit, 2)}", "yellow"))

        except Exception as e:
            self.logger.log_message("error", f"Error in check_stoploss: {e}")

    async def place_order_handler(self, data, prev_position, hard_squareoff=False):
        time.sleep(self.offset)
        response_codes = [0, 0, 0, 0]
        if hard_squareoff:
            position = "squareoff"
            response = self.read_daily_json()
            response['Position'] = position
            self.write_daily_json(response)
        else:
            position = data["position"]

        if position == "hold":
            print("Ignoring hold position")
            return [200, 200, 200, 200]
        
        # ignore tradesheet square off
        if position == "squareoff" and time.localtime().tm_hour == 15 and time.localtime().tm_min >= 15 and time.localtime().tm_min <= 30 and not hard_squareoff:
            print("Ignoring squareoff from the tradesheet")
            return [200, 200, 200, 200]
        

        instruments = [int(data["atmce"]), int(data["atmpe"]), int(data["wce"]), int(data["wpe"])]
        strike_prices = [int(data["atmSP"]), int(data["atmSP"]), int(data["wingCall"]), int(data["wingPut"])]

        
        self.set_multiplier()

        positions = {'beginx': [-1, -1, 1, 1], 'buy': [0, -2, 2, 2], 'sell': [-2, 0, 2, 2], 'squareoff': [0, 0, 0, 0], 'hold': [0, 0, 0, 0]}
        print(f"Taking Position: {position}")

        if position == "beginx":
            quantity = self.__multiplier * self.__base_quantity
            response = self.read_daily_json()
            response['highest_m2m'] = 0
            response['Date']=time.strftime("%Y-%m-%d")
            self.write_daily_json(response)
            # stoploss_sheet set 'quantity' to quantity
            self.trade_sheet = self.read_trade_sheet()
        else:
            self.trade_sheet = self.read_trade_sheet()
            quantity = self.__multiplier * self.__base_quantity      

        order_requests = []
        order_ids = []
        for order_type in ["BUY", "SELL"]:
            for i in range(4):

                previous_leg_position = positions[prev_position][i]
                leg_position = positions[position][i]

                # taking the difference of the leg position
                # example going from squareoff to beginx for leg 1
                # leg_position = -1, previous_leg_position = 0, hence leg_position_diff = -1, hence sell side
                # example going from beginx to buy for leg 1
                # leg_position = 0, previous_leg_position = -1, hence leg_position_diff = 1, hence buy side

                leg_position_diff = leg_position - previous_leg_position
                if leg_position_diff == 0:
                    print(f"Leg: {i}, No change in position")
                    response_codes[i] = 200
                    continue

                orderSide = "BUY" if leg_position_diff > 0 else "SELL" # If leg_position_diff is positive, then buy, else sell

                if orderSide == order_type:
                    orderQuantity = quantity * abs(leg_position_diff)
                    exchangeInstrumentID = int(instruments[i])

                    order_requests.append({
                        "exchangeSegment": "NSEFO",
                        "exchangeInstrumentId": str(exchangeInstrumentID),
                        "orderType": "MARKET",
                        "orderSide": orderSide,
                        "orderValidity": "1",
                        "quantity": orderQuantity,
                        "price": float(0),
                        "clientId": constants.CLIENT_MASTER["clientId"],
                        "strategyId": constants.CLIENT_MASTER["strategyId"],
                    })
                    

            
            tasks = [self.place_order(order) for order in order_requests]
            self.logger.log_message("info", f"Placing orders for {order_requests}")
            order_ids_temp = await asyncio.gather(*tasks)
            order_ids.extend(order_ids_temp)
            order_requests = []
        time.sleep(1)
        status_tasks = [self.pull_order_status(order_id) for order_id in order_ids]
        orders_status = await asyncio.gather(*status_tasks)
 
        # Create a dictionary to map instrument IDs to their order in the instruments list
        instrument_order = {instrument: idx for idx, instrument in enumerate(instruments)}

        # Print the instrument_order dictionary for debugging
        print(f"{instrument_order=}")

        # Sort the orders_status based on the instrument order, converting exchangeInstrumentId to integer
        orders_status = sorted(orders_status, key=lambda x: instrument_order.get(int(x['exchangeInstrumentId']), float('inf')))


        for i, order_status in enumerate(orders_status):
            if order_status["status"] == "filled":
                print(f"Order {order_status}")
                order_side = order_status["orderSide"].capitalize()
                order_price = order_status["placedPrice"]
                placed_quantity = order_status["placedQuantity"]
                exchangeInstrumentID = int(order_status["exchangeInstrumentId"])
                

                
                # create a new row in the trade sheet if trading symbol is not present, it is not based on index
                if exchangeInstrumentID not in self.trade_sheet['InstrumentID'].values:
                    # Create a new row with default values for other columns and TradingSymbol as trading_symbol
                    new_row = pd.DataFrame([{col: 0 for col in self.trade_sheet.columns}])
                    new_row.at[0, 'InstrumentID'] = exchangeInstrumentID
                    
                    # Append the new row using pd.concat
                    self.trade_sheet = pd.concat([self.trade_sheet, new_row], ignore_index=True)
        

                # Update the existing row
                condition = self.trade_sheet['InstrumentID'] == exchangeInstrumentID

                # self.trade_sheet.loc[condition, 'TradingSymbol'] = trading_symbol
                
                current_qty = float(self.trade_sheet.loc[condition, f'{order_side}Quantity'].iloc[0])

                current_avg_price = float(self.trade_sheet.loc[condition, f'{order_side}AveragePrice'].iloc[0])
                print(float(self.trade_sheet.loc[condition, f'{order_side}AveragePrice']))
                print(f"{current_qty=}, {current_avg_price=}")
                new_avg_price = ((current_avg_price * current_qty) + (order_price * placed_quantity)) / (current_qty + placed_quantity)
                self.trade_sheet.loc[condition, f'{order_side}AveragePrice'] = float(new_avg_price)
                self.trade_sheet.loc[condition, f'{order_side}Quantity'] += placed_quantity

                self.trade_sheet.loc[condition, 'LegPosition'] = positions[position][i]
                self.trade_sheet.loc[condition, 'NetQuantity'] = self.trade_sheet.loc[condition, 'BuyQuantity'] - self.trade_sheet.loc[condition, 'SellQuantity']
                
                self.write_trade_sheet(self.trade_sheet)

                self.logger.log_message("info", f"Order placed for ; Instrument: {exchangeInstrumentID}; OrderSide: {order_side}; Quantity: {placed_quantity}")
                self.telegramBot.send_message(f"Order placed for\n\nTicker:{strike_prices[i]}\nOrderSide: {order_side}\nQuantity: {placed_quantity}\nOrderPrice: {order_price}")

            elif order_status["status"] == "rejected":
                print(f"Order {order_status}")
                response_codes[i] = 400
                self.logger.log_message("error", f"Order rejected for ; Instrument: {order_status['exchangeInstrumentId']}")
                self.telegramBot.send_message(f"Order rejected for\n\nTicker:{strike_prices[i]}")

            if 400 not in response_codes:
                response_codes = [200] * len(response_codes)           
            

        
        if position == "squareoff":
            m2m = self.calculate_m2m(position)
            self.cycle_count += 1
            self.write_cycle_count(self.cycle_count)

            self.trade_sheet = pd.DataFrame(columns=['TradingSymbol', 'InstrumentID', 'CMP', 'LegPosition', 'BuyAveragePrice', 'BuyQuantity', 'SellAveragePrice', 'SellQuantity', 'NetQuantity', 'UnrealisedM2M', 'RealisedM2M', 'M2M'], index=None)
            self.file_creator.check_and_create_tradesheet(f"Tradesheets/{self.__equity}_trade_sheet_cycle{self.cycle_count}.csv")
           
            response = self.read_daily_json()
            response['highest_m2m'] = 0
            response['Date']= time.strftime("%Y-%m-%d")
            realised_m2m = response['Realised M2M']
            response['Booked'] = response['Booked'] + realised_m2m
            response['Realised M2M'] = 0
            response['Unrealised M2M'] = 0
            response['Current M2M'] = 0
            response['Position'] = "squareoff"
            self.write_daily_json(response)
            
        if hard_squareoff:
            self.logger.log_message("info", "Hard squareoff completed")
            self.telegramBot.send_message("Hard squareoff completed")
        return response_codes

    async def place_order(self, order_data: dict) -> str:
        try:
            print(colored(f"Placing order for {order_data}", "yellow"))
            async with httpx.AsyncClient() as client:
                response = await client.post(self.endpoints['place_order'][0], json=order_data)
                response.raise_for_status()
                order_id = response.json().get("orderId")
                return order_id
        except Exception as e:
            self.logger.log_message("error", f"Error in place_order: {e}")


# from concurrent.futures import ThreadPoolExecutor, as_completed


# def main():
#     api = SymphonyInteractiveAPI(25, "NIFTY15", None)
#     funds = api.get_total_funds()
#     print(f"Funds: {funds}")

    # order_params = {
    #     "exchangeSegment": "NSEFO",
    #     "exchangeInstrumentID": 64444,
    #     "productType": "NRML",
    #     "orderType": "LIMIT",
    #     "orderSide": "BUY",
    #     "timeInForce": "DAY",
    #     "disclosedQuantity": 0,
    #     "orderQuantity": 25,
    #     "limitPrice": 0.5,
    #     "stopPrice": 0,
    #     "orderUniqueIdentifier": "454845",
    #     "clientID": "*****",
    # }

    # with ThreadPoolExecutor(max_workers=500) as executor:
    #     futures = [executor.submit(api.place_order, **order_params) for _ in range(400)]
        
    #     for future in as_completed(futures):
    #         response = future.result()
    #         print(response.json())

if __name__ == "__main__":
    main()