import asyncio
from twisted.internet import asyncioreactor

# On Windows, ensure to use SelectorEventLoop instead of ProactorEventLoop
if asyncio.get_event_loop_policy().__class__.__name__ == 'WindowsProactorEventLoopPolicy':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Now install the Twisted asyncio reactor
# asyncioreactor.install()

# Explicitly prevent Twisted from setting up signals
import twisted.internet._signals
twisted.internet._signals.install = lambda *args, **kwargs: None

# Rest of your imports
from strategy import SpotBrain, OptionsBrain, CMPPutter
from file_engine import FileCreator, FileResetter
from logging_config import CustomLogger
import constants
from datetime import datetime
import pandas as pd
import sys
import zmq.asyncio
import pickle

import time
from zerodha_final_engine import KiteDataEngine, SpotCandleEngine, OptionsCandleEngine, MarketDataStreamer  # Replace with Zerodha API
import json

DF_15MIN = None
SPOT_DF = None

async def main(instrument_id, equity, strike, wings, base_qty, freeze_qty, series):
    # Initialize the Kite Data Engine (Zerodha)
    kite_data_engine = KiteDataEngine()
    
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.PUB)
    
    # Bind the socket to a TCP address and port
    socket.bind("tcp://*:5555")  # Binds to all available interfaces on port 5555
    print("Publisher started and bound to port 5555.")


    cmp_socket = context.socket(zmq.PUB)
    cmp_socket.bind("tcp://*:5556")
    print("CMP Publisher started and bound to port 5556.")

    # Initialize new_equity variable regardless of equity value
    equity = equity.upper()
    new_equity = equity
    if equity == 'NIFTY1' or equity == 'NIFTY15' or equity == 'NIFTY':
        new_equity = 'NIFTY 50'
    # Ensure new_equity is properly set
    if not new_equity:
        raise ValueError("Error: 'new_equity' is not initialized.")

    # Initialize the SpotCandleEngine, OptionsCandleEngine with the Zerodha Kite API
    spot_candle_engine = SpotCandleEngine(kite=kite_data_engine.kite, symbol=new_equity, loop=asyncio.get_event_loop())
    options_candle_engine = OptionsCandleEngine(kite=kite_data_engine.kite, spot_symbol=new_equity, loop=asyncio.get_event_loop())
    spot_instrument_token = spot_candle_engine.get_spot_instrument_token()

    # Fetch spot OHLC data once
    response_df = await spot_candle_engine.fetch_ohlc_once(spot_instrument_token)
    if response_df is None or response_df.empty:
        print("Error: Failed to fetch OHLC data for spot.")
        sys.exit(1)

    # Resample spot data to 15-minute intervals
    await spot_candle_engine.update_dataframe_15min_ohlc(response_df)
    latest_candle = await spot_candle_engine.get_latest_15min_candle()
    close_price = latest_candle['Close']

    # Get the options instruments
    strike = int(strike)
    options_instruments = await options_candle_engine.get_options_instruments()

    market_streamer = MarketDataStreamer(kite=kite_data_engine.kite, spot_engine=spot_candle_engine, options_engine=options_candle_engine, loop=asyncio.get_event_loop())
    
    # Start the market data streamer
    market_streamer.start()

    df_instruments = await options_candle_engine.get_instruments_df()
    options_symbol = options_candle_engine.map_symbol_to_options()
    closest_expiry = options_candle_engine.get_closest_expiry(df_instruments,options_symbol)
    print(f'Closest expiry is : {closest_expiry}')
    # Initialize the SpotBrain and OptionsBrain
    spot_brain = SpotBrain(equity=equity)
    options_brain = OptionsBrain(equity=equity, strike=strike, closest_expiry_date=closest_expiry)
    
    # Populate the strike-instrument map in the options brain
    await options_brain.populate_map_strike_instrument(options_candle_engine.map_strike_instrument)

    # Initialize StopLossBrain
    print(f'New equity is : {new_equity} and equity is : {equity}')
    cmp_putter = CMPPutter(kite_data_engine.kite, equity, options_candle_engine)

    
    
    # Start the candle engine and run SpotBrain concurrently
    await asyncio.gather(
        spot_brain_loop(spot_brain, spot_candle_engine,spot_instrument_token),
        options_brain_loop(options_brain, options_candle_engine, cmp_putter, socket),
        cmp_putter_loop(cmp_putter, cmp_socket),
    )

async def spot_brain_loop(spot_brain, spot_candle_engine,spot_instrument_token):
    global DF_15MIN, SPOT_DF
    while True:
        try:
            response_df = await spot_candle_engine.fetch_ohlc_once(spot_instrument_token)
            if response_df is not None and not response_df.empty:

                await spot_candle_engine.update_dataframe_15min_ohlc(response_df)
                # Assume that MarketDataStreamer is feeding live data into spot_candle_engine
                DF_15MIN = await spot_candle_engine.resample_ohlc(interval ='15min')

                if DF_15MIN is None or DF_15MIN.empty:
                    print("Error: Failed to resample spot data to 15-minute intervals.")
                    continue
                
                # Populate SpotBrain with the resampled data and run the strategy
                await spot_brain.populate_dataframe(DF_15MIN)
                await spot_brain.run()
                
                
                SPOT_DF = await spot_brain.get_df()
            else:
                print("Error: Failed to fetch OHLC data for spot.")
                continue
        except Exception as e:
            print(f"Error in spot_brain_loop: {e}")

        await asyncio.sleep(constants.LOOP_SLEEP)

async def options_brain_loop(options_brain, options_candle_engine, cmp_putter, socket):
    global SPOT_DF
    while True:
        # Populate OptionsBrain with the live spot data and run the strategy
        await options_brain.populate_dataframe(SPOT_DF)
        options_df = await options_brain.run()
        await cmp_putter.populate_dataframe(options_df)

        # Serialize the DataFrame using pickle
        serialized_df = pickle.dumps(options_df)

        # Send the serialized DataFrame
        socket.send(serialized_df)

        # You can save the options data if needed here
        
        await asyncio.sleep(constants.LOOP_SLEEP)

async def cmp_putter_loop(cmp_putter, cmp_socket):
    while True:
        print("Getting current price dict...")
        current_price_dict = await cmp_putter.get_current_price()
        print(f"Current price dict: {current_price_dict}")
        # Serialize the current price dictionary using pickle
        serialized_dict = pickle.dumps(current_price_dict)
        cmp_socket.send(serialized_dict)

        await asyncio.sleep(constants.LOOP_SLEEP)

def get_equity_data(equity):
    with open(constants.EQUITY_DATA_PATH, 'r') as f:
        data = json.load(f)
        return data[equity]

if __name__ == "__main__":
    try:
        first_iteration = 0
        equity = sys.argv[1].upper()
        equity_data = get_equity_data(equity)
        instrument_id = equity_data['exchangeInstrumentID']
        strike = equity_data['Strike']
        wings = equity_data['Wings']
        base_qty = equity_data['base_qty']
        freeze_qty = equity_data['freeze_qty']
        series = equity_data['series']

        if equity == 'NIFTY1' or equity == 'NIFTY15':
            today = datetime.today().weekday()
            if today == 0:
                wings = 400
            elif today == 1:
                wings = 300
            elif today == 2:
                wings = 200
            elif today == 3:
                wings = 100
            elif today in [4, 5, 6]:
                wings = 400
            print(f"{wings=}")


        # Run the main event loop
        asyncio.run(main(
            instrument_id=instrument_id,
            equity=equity,
            strike=strike,
            wings=wings,
            freeze_qty=freeze_qty,
            base_qty=base_qty,
            series=series
        ), debug=True)

    except Exception as e:
        print(e)
        logger = CustomLogger('main.py', equity=equity)
        logger.log_message('error', f"Error in main.py: {e}")
