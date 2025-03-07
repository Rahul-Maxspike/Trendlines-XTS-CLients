from trailing_stoploss_ordering_engine import SymphonyInteractiveAPI
import asyncio
import pandas as pd
import time
import constants
from logging_config import CustomLogger, TelegramBot, ConfirmationPopup
from file_engine import FileCreator, FileSaver, FileResetter
from datetime import datetime, timedelta
import json
import sys 
import tkinter as tk
import zmq
import pickle
# Create the root window
root = tk.Tk()
root.withdraw()  # Hide the root window

# Initialize the Telegram Bot
telegram_bot = TelegramBot()

def get_equity_data(equity):
    with open(constants.EQUITY_DATA_PATH, 'r') as f:
        data = json.load(f)
        return data[equity]
    
async def update_candles_data(equity, response_codes):
    """Updates the JSON file with new response codes for legs, resetting if necessary."""
    file_path = f"daily_jsons/{equity}.json"
    
    try:
        # Read the existing data from the file
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Update the 'leg' values in the data
        for i in range(4):
            data[f'leg{i+1}'] = response_codes[i]
        
        # Write the updated data back to the file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        
    except json.JSONDecodeError as e:
        file_resetter = FileResetter(equity)
        print(f"Error decoding JSON from file {file_path}: {e}")
        file_resetter.reset_daily_json()  # Reset the file if JSON decoding fails
        # After resetting, try updating the response codes again
        update_candles_data(equity, response_codes)  # Reattempt to update after resetting
    except Exception as e:
        print(f"An error occurred: {e}")
        await file_resetter.reset_daily_json()  # Reset the file if JSON decoding fails
        # After resetting, try updating the response codes again
        update_candles_data(equity, response_codes)  # Reattempt to update after resetting

def squareoff_last_updated_on_sheet(position, df_options_data, equity, caller, response_codes=[200, 200, 200, 200], datetime_value=datetime.now().strftime("%Y-%m-%d %H:%M:%S")):
    # read write to daily_json the resposne codes
    print(f"{caller= }")
    update_candles_data(equity, response_codes)
    df_options_data_last_row = df_options_data.iloc[-1].copy()
    # put last rows date with time 15:30
    df_options_data_last_row['Datetime'] = datetime_value
    df_options_data_last_row['position'] = position
    # append the last row to the df
    df_options_data.loc[len(df_options_data)] = df_options_data_last_row
    df_options_data.loc[df_options_data.index[-1], ['atmceS', 'atmpeS', 'wingceS', 'wingpeS']] = [200, 200, 200, 200]
    df_options_data.to_csv(f"equities/{equity}_last_update_options_brain.csv", index=False)
    


async def main():
    try:
        global logger

        # Initialize ZeroMQ context and Subscriber socket
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect("tcp://localhost:5555")  # Assumes Publisher is running on the same machine

        cmp_socket = context.socket(zmq.SUB)
        cmp_socket.connect("tcp://localhost:5556")

        
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        print("Subscriber connected to publisher at port 5555.")
        cmp_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        print("CMP Subscriber connected to publisher at port 5556.")

        
        try:
            equity = sys.argv[1].upper()
            equity_data = get_equity_data(equity)
            print(equity)
            #logger
            logger = CustomLogger('order_placer_main.py',equity = equity)
            base_qty = equity_data['base_qty']
            offset = equity_data['Offset']
            freeze_qty = equity_data['freeze_qty']

            file_creator = FileCreator(equity)
            file_creator.create_files_if_not_exist()
            #for squareoff comment the below lines
            file_resetter = FileResetter(equity)
            file_resetter.reset_if_needed()
        except Exception as e:
            print(e)

        

        

        api = SymphonyInteractiveAPI(base_qty=base_qty, equity=equity, offset=offset,freeze_qty=freeze_qty)
    
    
        # Read the initial trade sheet data
        df_options_data = pd.read_csv(f"equities/{equity}_last_update_options_brain.csv")
        has_hard_squareoff = False

        # Check if the last entry in last_update_options_brain.csv is of the current date
        last_datetime = df_options_data.iloc[-1]['Datetime']
        last_day = int(last_datetime.split()[0].split("-")[2])  # Extract the day part from the timestamp
        current_day = time.localtime().tm_mday
        if current_day == last_day:
            # if time is past 15:30
            # check if atmceS, atmpeS, wingceS, wingpeS are not 200 for last row
            # if so then remove last row
            if df_options_data.iloc[-1]['position'] == "hard-squareoff":
                print("Exiting because of hard squareoff on same day")
                quit()
                
            try:
                if df_options_data.iloc[-1]['atmceS'] != 200 or df_options_data.iloc[-1]['atmpeS'] != 200 or df_options_data.iloc[-1]['wingceS'] != 200 or df_options_data.iloc[-1]['wingpeS'] != 200:
                    df_options_data = df_options_data.iloc[:-1]
                    df_options_data.to_csv(f"equities/{equity}_last_update_options_brain.csv", index=False)
            except:
                pass

            if time.localtime().tm_hour == 16 and time.localtime().tm_min >= 30:
                squareoff_last_updated_on_sheet("squareoff", df_options_data, equity, datetime_value=df_options_data.iloc(-1, ['Datetime']).split()[0] + " 15:30:00", caller="15:30")

            if df_options_data.iloc[-1]['position'] == "hard-squareoff":
                print("Exiting because of hard squareoff on same day")
                quit()
            last_data = df_options_data.iloc[-1]
            # if not, then create a new csv file
            positions = {'beginx': [-1, -1, 1, 1], 'buy': [0, -2, 2, 2], 'sell': [-2, 0, 2, 2], 'squareoff': [0, 0, 0, 0], 'hold': [0, 0, 0, 0]}
            api.trade_sheet = api.read_trade_sheet()



            
        while True:
            # Read the latest trade sheet data
            now = datetime.now()
            # Calculate the closest lower 15-minute interval
            closest_15_min_lower = now.minute - (now.minute % 15)
            date_time_lower = now.replace(minute=closest_15_min_lower, second=0, microsecond=0) - timedelta(minutes=15)
            # Calculate the closest upper 15-minute interval
            date_time_upper = date_time_lower + timedelta(minutes=30)

            try:
                # Receive the serialized DataFrame
                serialized_df = socket.recv()
                latest_df = pickle.loads(serialized_df)
                
                # latest_df = pd.read_csv(f"equities/{equity}_options_brain.csv")
                # last_row_time = datetime.strptime(latest_df.iloc[-1]['Datetime'], "%Y-%m-%d %H:%M:%S")
                last_row_time = latest_df.iloc[-1]['Datetime']
                if not (date_time_lower <= last_row_time < date_time_upper):
                    print("Not in the same 15 min interval")
                    continue
            
            except Exception as e:
                print(f"Error reading latest data: {e}")
                time.sleep(1)
                continue

            # Identify new trades based on changes in the last row's "position" value
            latest_position = latest_df.iloc[-1]['position']
            prev_position = df_options_data.iloc[-1]['position']
            placed_instruments = latest_df.iloc[-1][['atmce', 'atmpe', 'wce', 'wpe']].to_dict()


            if latest_position != prev_position:
                # check if we are in the same 15 min interval as the last trade
                latest_datetime = str(latest_df.iloc[-1]['Datetime'])
                latest_hour = int(latest_datetime.split()[1].split(":")[0])
                latest_minute = int(latest_datetime.split()[1].split(":")[1])

                # if not time.localtime().tm_hour == latest_hour and time.localtime().tm_min == latest_minute:
                #     # compare the date as well
                #     if not time.localtime().tm_mday == int(latest_datetime.split()[0].split("-")[2]):
                #         print("Not executing because of different time interval")
                #         continue
                

                # Place the order using the SymphonyInteractiveAPI for the last trade
                print("Placing order...")
                telegram_bot.send_message(f"{equity} Placing order for {latest_df.iloc[-1]['position']}")
                # response_codes = api.place_order_handler(latest_df.iloc[-1], latest_df.iloc[-2]['position'])
                time.sleep(offset)
                response_codes = await api.place_order_handler(latest_df.iloc[-1], prev_position)
                
                if latest_position == "squareoff" and latest_hour == "15" and latest_minute >= "15":
                    print("Not executing because of squareoff at 15:15")
                else:
                    # sum the response codes to check if all orders were placed successfully
                    # check if all response codes are 200
                    df_options_data = latest_df
                    # write to the last row of df df_options_data
                    df_options_data.loc[df_options_data.index[-1], ['atmceS', 'atmpeS', 'wingceS', 'wingpeS']] = response_codes
                    update_candles_data(equity, response_codes=response_codes)
                    df_options_data.to_csv(f"equities/{equity}_last_update_options_brain.csv", index=False)

                    if all([response == 200 for response in response_codes]):
                        print("All orders placed successfully")
                    else:
                        print("Some orders failed to place, respose codes: ", response_codes)
                        # Create the root window
                        root = tk.Tk()
                        root.withdraw()  # Hide the root window
                                        

                        # Create and show the confirmation popup
                        confirmation_popup = ConfirmationPopup(root,f"{equity}\nSome orders failed to place, respose codes: " + str(response_codes) + "\nDo you want to continue?")
                        result = confirmation_popup.show()
                        
                        if result == "No":
                            print("Exiting")
                            quit()
                        else:
                            df_options_data.loc[df_options_data.index[-1], ['atmceS', 'atmpeS', 'wingceS', 'wingpeS']] = [200, 200, 200, 200]
                            df_options_data.to_csv(f"equities/{equity}_last_update_options_brain.csv", index=False)
                            update_candles_data(equity, response_codes=[200, 200, 200, 200])
                            
                            root.quit()




                # check if time is past 15:00 or is 15:00 and less than 30 minutes
                # then check if position is squareoff
                # if no, then squareoff all positions
            
            # checking stop loss
            serialized_dict = cmp_socket.recv()
            cmp_dict = pickle.loads(serialized_dict)
            is_stop_loss = api.check_stoploss(latest_position, placed_instruments, cmp_dict)

            if (time.localtime().tm_hour == 15 and time.localtime().tm_min >= 15 and time.localtime().tm_min <= 30) or is_stop_loss:
                if not is_stop_loss:
                    time.sleep(offset)
                if not has_hard_squareoff:
                    telegram_bot.send_message(f"{equity} Placing order for Auto Squareoff")
                    response_codes = await api.place_order_handler(latest_df.iloc[-1], prev_position, hard_squareoff=True)
                    
                    # write to the last row of df df_options_data
                    print(response_codes)
                    squareoff_last_updated_on_sheet("hard-squareoff", df_options_data, equity, "hard-squareoff", response_codes)
                    if all([response == 200 for response in response_codes]):
                        print("All squareoff orders placed successfully")
                        has_hard_squareoff = True
                        file_saver = FileSaver(equity)
                        file_saver.save_files()
                        quit()
                    else:

                        print("Some squareoff orders failed to place")
                        # Create the root window
                        root = tk.Tk()
                        root.withdraw()  # Hide the root window
                        # Create and show the confirmation popup
                        confirmation_popup = ConfirmationPopup(root, f"{equity}Some orders failed to place, respose codes: " + str(response_codes) + "\nDo you want to continue?")
                        result = confirmation_popup.show()
                        
                        if result == "No":
                            print("Exiting")
                            quit()
                        else:
                            df_options_data.loc[df_options_data.index[-1], ['atmceS', 'atmpeS', 'wingceS', 'wingpeS']] = [200, 200, 200, 200]
                            df_options_data.to_csv(f"equities/{equity}_last_update_options_brain.csv", index=False)
                            update_candles_data(equity, response_codes=[200, 200, 200, 200])
                            root.quit()
                else:
                    pass
            else:
                has_hard_squareoff = False

            positions = {'beginx': [-1, -1, 1, 1], 'buy': [0, -2, 2, 2], 'sell': [-2, 0, 2, 2], 'squareoff': [0, 0, 0, 0], 'hold': [0, 0, 0, 0]}

                

            # Wait for a specified interval before checking for updates again
            # time.sleep(constants.ORDER_PLACER_INTERVAL)
    except KeyboardInterrupt:
        print("\nOrder Placer interrupted and shutting down.")
    finally:
        socket.close()
        context.term()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())