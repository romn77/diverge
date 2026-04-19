import requests
import os
from dotenv import load_dotenv
load_dotenv()   
# massive
url = "http://35.209.101.63/api/v1/market/stocks/bars"
headers = { "X-API-KEY": os.getenv("MASSIVE_API_KEY") }
params = {
    "tickers": ["NVDA"], #可以一次请求多个股票代码
    "interval": "1Day",
    "start_time": "2016-01-01T00:00:00Z"
}
response = requests.get(url, headers=headers, params=params)
print(response.json())