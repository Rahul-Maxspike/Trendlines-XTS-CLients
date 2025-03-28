#
##################
# CONSTANTS FILE #
##################
#
# Do Not Tamper with the values of the constants
#
#
########################################################
# Program Logic Constants
FETCH_INTERVAL_SECONDS = 5
LOOP_SLEEP = 0.1
UPDATE_15MIN_DF_INTERVAL = 10
compression_value_15_min = 900
compression_value_1_min = 60
ORDER_PLACER_INTERVAL = 5
########################################################
#
#
########################################################
#
########################################################
#
# CREDETIALS API
URL_CREDENTIAL_API_ZEORDHA_TOKEN = "http://110.172.21.62:5005/token/zerodha"
#
########################################################
#
#
########################################################
# Spot Brain Constants
WINDOW = 14 # window for 15-minute candles
FAST_FACTOR = 2.0
SLOW_FACTOR = 30.0
DF_15MIN_BACK_DAYS = 6
########################################################
# Client Master Data
CLIENT_MASTER = {
    "uri": "http://110.172.21.62:5010",
    "clientId": "MaxAJNI0402",
    "strategyId": "M4A1"
}
#
#
########################################################
#OMS CONSTANTS
OMS_URI = "http://192.168.1.8:7004/api/v1/orders/"
########################################################
# Telegram Bot Constants
TELEGRAM_BOT_TOKEN = "6418611543:AAFgPRBSBjiaSpcH8pJawpaWUrkjN_AOrto"
TRENDLINES_CHAT_ID = "-4222452040"
#
#
########################################################
# File Paths
DAILY_JSON_PATH = "daily.json"
HEADERS_PATH = "headers.json"
EQUITY_DATA_PATH = "equity_data.json"

