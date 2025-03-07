import os
import pandas as pd
import json
from datetime import datetime
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

filesaver_obj_nifty_1 = FileSaver('NIFTY1')
filesaver_obj_nifty_1.save_files()
filesaver_obj_nifty_15 = FileSaver('NIFTY15')
filesaver_obj_nifty_15.save_files()