import requests
from kiteconnect import KiteConnect, KiteTicker

class KiteDataEngine:
    def __init__(self):
        self.access_token = self._get_access_token()
        # self.logger = logging.getLogger('MarketData')
        self.kite = KiteConnect(api_key="s4pnzfflytntrgmf")
        self.kite.set_access_token(self.access_token)


    def _get_access_token(self):
        response = requests.get("http://110.172.21.62:5005/token/zerodha")
        print(response.json())
        if response.status_code == 200:
            return response.json()

kitedataengine = KiteDataEngine()
print(kitedataengine.kite.ltp(256265))