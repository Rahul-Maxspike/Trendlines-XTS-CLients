# library imports
import pandas as pd
import json
import os
from datetime import datetime, timedelta



# this file will be used to reset the memory data
# files targetted are:
# 1. {equity}optionsdata.csv
# 2. {equity}optionsbrain-lastupdated
# 3. {equity}dailyjson
# 4. {equity}tradesheet.csv

class FileDeleter:
    def __init__(self, equity):
        self.equity = equity
        self.optionsbrain_lastupdated_path = f"./equities/{equity}_last_update_options_brain.csv"
        self.tradesheet_paths = self.get_tradesheet_paths()
        self.daily_json_path = f"./daily_jsons/{equity}.json"
        self.optionsbrain_path = f"./equities/{equity}_options_brain.csv"

    def get_tradesheet_paths(self):
        # target paths are:
        # "./Tradesheets/{equity}_trade_sheet_cycle1.csv"
        # "./Tradesheets/{equity}_trade_sheet_cycle2.csv"
        # "./Tradesheets/{equity}_trade_sheet_cycle3.csv"
        # check if the file exists, return paths for existing files
        paths = []
        for i in range(1, 10):
            path = f"./Tradesheets/{self.equity}_trade_sheet_cycle{i}.csv"
            if os.path.exists(path):
                paths.append(path)
        return paths
    
    def delete_files(self):
        self.delete_file(self.optionsbrain_lastupdated_path)
        self.delete_file(self.optionsbrain_path)
        self.delete_file(self.daily_json_path)
        for path in self.tradesheet_paths:
            self.delete_file(path)

    def delete_trade_sheets(self):
        for path in self.tradesheet_paths:
            self.delete_file(path)

    def delete_file(self, path):
        if os.path.exists(path):
            os.remove(path)
            print(f"Deleted: {path}")
    

class FileResetter:
    def __init__(self, equity):
        print(f"Resetting {equity}")
        self.equity = equity
        self.optionsbrain_lastupdated_path = f"./equities/{equity}_last_update_options_brain.csv"
        self.tradesheet_path = f"./Tradesheets/{equity}_trade_sheet_cycle1.csv"
        self.daily_json_path = f"./daily_jsons/{equity}.json"
        self.optionsbrain_path = f"./equities/{equity}_options_brain.csv"

    def reset_optionsbrain(self):
        # making the last position as 'squareoff'
        try:
            df = pd.read_csv(self.optionsbrain_path)
            last_position = df.iloc[-1]['position']
            if last_position != 'squareoff':
                df.loc[df.index[-1], 'position'] = 'squareoff'
                df.to_csv(self.optionsbrain_path, index=False)
                print(f"{self.optionsbrain_path} reset.")
        except FileNotFoundError:
            print(f"{self.optionsbrain_path} not found. Cannot reset.")

    def reset_optionsbrain_lastupdated(self):
        # copy the optionsbrain to optionsbrain_lastupdated
        try:
            df = pd.read_csv(self.optionsbrain_path)
            df.to_csv(self.optionsbrain_lastupdated_path, index=False)
            print(f"{self.optionsbrain_lastupdated_path} reset.")
        except FileNotFoundError:
            print(f"{self.optionsbrain_path} not found. Cannot reset.")

    def reset_tradesheet(self):
        # Columns are TradingSymbol,InstrumentID,CMP,LegPosition,BuyAveragePrice,BuyQuantity,SellAveragePrice,SellQuantity,NetQuantity,UnrealisedM2M,RealisedM2M,M2M
        columns = ['TradingSymbol', 'InstrumentID', 'CMP', 'LegPosition', 'BuyAveragePrice', 'BuyQuantity', 'SellAveragePrice', 'SellQuantity', 'NetQuantity', 'UnrealisedM2M', 'RealisedM2M', 'M2M']
        df = pd.DataFrame(columns=columns)
        df.to_csv(self.tradesheet_path, index=False)
        print(f"{self.tradesheet_path} reset.")

    def reset_daily_json(self):
        # data is
        # {"highest_m2m": 0, "Current M2M": 0, "Stoploss Price": 0, "Position": "squareoff", "leg1": 200, "leg2": 200, "leg3": 200, "leg4": 200, "Date": ""}
        data = {"highest_m2m": 0, "Current M2M": 0, "Stoploss Price": 0, "Realised M2M": 0, "Unrealised M2M": 0, "Booked": 0, "Position": "squareoff", "leg1": 200, "leg2": 200, "leg3": 200, "leg4": 200, "Date": "", "Cycle Count": 1}
        with open(self.daily_json_path, 'w') as f:
            json.dump(data, f)
        print(f"{self.daily_json_path} reset.")


    def get_last_date_from_csv(self, file_path):
        try:
            df = pd.read_csv(file_path)
            if not df.empty:
                last_date = df.iloc[-1]['Datetime']
                print(f"{file_path=}, {last_date=}")
                # Parse the datetime string and extract the date part
                last_date = datetime.strptime(last_date, '%Y-%m-%d %H:%M:%S').date()
                return last_date
            else:
                print(f"{file_path} is empty.")
        except FileNotFoundError:
            print(f"{file_path} not found.")



    def reset_if_needed(self):
        try:

            
            
            today = datetime.today().date()

            lastupdated_date = self.get_last_date_from_csv(self.optionsbrain_lastupdated_path)
            optionsbrain_date = self.get_last_date_from_csv(self.optionsbrain_path)

            if (lastupdated_date is None or optionsbrain_date is None or 
                lastupdated_date != today or optionsbrain_date > lastupdated_date):
                self.reset_optionsbrain()
                self.reset_optionsbrain_lastupdated()
                self.reset_tradesheet()
                self.reset_daily_json()
                FileDeleter(self.equity).delete_trade_sheets()
                FileCreator(equity=self.equity).check_and_create_tradesheet(self.tradesheet_path)
                print("***Files have been succesfully reset!***")
        except Exception as e:
            print(f"Error in reset_if_needed: {e}")


class FileCreator:
    def __init__(self, equity):
        self.equity = equity
        self.optionsbrain_path = f"./equities/{equity}_options_brain.csv"
        self.optionsbrain_lastupdated_path = f"./equities/{equity}_last_update_options_brain.csv"
        self.tradesheet_path = f"./Tradesheets/{equity}_trade_sheet_cycle1.csv"
        self.daily_json_path = f"./daily_jsons/{equity}.json"


    def create_files_if_not_exist(self):
        self.create_folder_if_not_exist('./logs')
        self.create_folder_if_not_exist('./saved_data')
        self.create_folder_if_not_exist('./equities')
        self.create_folder_if_not_exist('./Tradesheets')
        self.create_folder_if_not_exist('./daily_jsons')
        self.check_and_create_options_brain()
        self.check_and_create_options_brain_lastupdated()
        self.check_and_create_tradesheet(self.tradesheet_path)
        self.check_and_create_json(self.daily_json_path)

    def create_folder_if_not_exist(self, path):
        os.makedirs(path, exist_ok=True)

    def check_and_create_options_brain(self):
        if not os.path.exists(self.optionsbrain_path):
            columns=['Datetime','Open','High','Low','Close', 'position']
            df = pd.DataFrame(columns=columns)
            # add the Datetime as today and open high low close as 0
            df.loc[0] = [datetime.today().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 'squareoff']
            df.to_csv(self.optionsbrain_path, index=False)
    
    def check_and_create_options_brain_lastupdated(self):
        if not os.path.exists(self.optionsbrain_lastupdated_path):
            columns=['Datetime','Open','High','Low','Close', 'position']
            df = pd.DataFrame(columns=columns)
            # add the Datetime as today - 1 day and open high low close as 0, position as squareoff
            df.loc[0] = [(datetime.today()-timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 'squareoff']
            df.to_csv(self.optionsbrain_lastupdated_path, index=False)
    
    def check_and_create_tradesheet(self, path):
        columns=['TradingSymbol', 'InstrumentID', 'CMP', 'LegPosition', 'BuyAveragePrice', 'BuyQuantity', 'SellAveragePrice', 'SellQuantity', 'NetQuantity', 'UnrealisedM2M', 'RealisedM2M', 'M2M']
        if not os.path.exists(path):
            df = pd.DataFrame(columns=columns)
            df.to_csv(path, index=False)

    def check_and_create_json(self, path):
        if not os.path.exists(path):
            data = {"highest_m2m": 0, "Current M2M": 0, "Stoploss Price": 0, "Realised M2M": 0, "Unrealised M2M": 0, "Booked":0, "Position": "squareoff", "leg1": 200, "leg2": 200, "leg3": 200, "leg4": 200, "Date": "", "Cycle Count": 1}
            with open(path, 'w') as f:
                json.dump(data, f)


class FileSaver:
    def __init__(self, equity):
        self.equity = equity
        self.optionsbrain_lastupdated_path = f"./equities/{equity}_last_update_options_brain.csv"
        self.tradesheet_paths = self.get_tradesheet_paths()
        self.daily_json_path = f"./daily_jsons/{equity}.json"
        self.optionsbrain_path = f"./equities/{equity}_options_brain.csv"
    
    def get_tradesheet_paths(self):
        # target paths are:
        # "./Tradesheets/{equity}_trade_sheet_cycle1.csv"
        # "./Tradesheets/{equity}_trade_sheet_cycle2.csv"
        # "./Tradesheets/{equity}_trade_sheet_cycle3.csv"
        # check if the file exists, return paths for existing files
        paths = []
        for i in range(1, 10):
            path = f"./Tradesheets/{self.equity}_trade_sheet_cycle{i}.csv"
            if os.path.exists(path):
                paths.append(path)
        return paths



    def save_files(self):
        self.save_csv(self.optionsbrain_lastupdated_path)
        self.save_csv(self.optionsbrain_path)
        self.save_json(self.daily_json_path)
        for path in self.tradesheet_paths:
            self.save_csv(path)

    def get_save_path(self, path):
        today = datetime.today()
        year = today.year
        month = today.month
        day = today.day
        save_dir = f"./saved_data/{year}/{month}/{day}"
        os.makedirs(save_dir, exist_ok=True)
        return os.path.join(save_dir, os.path.basename(path))

    def save_csv(self, path):
        if os.path.exists(path):
            df = pd.read_csv(path)
            save_path = self.get_save_path(path)
            df.to_csv(save_path, index=False)
            print(f"Saved CSV: {save_path}")

    def save_json(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            save_path = self.get_save_path(path)
            with open(save_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved JSON: {save_path}")
