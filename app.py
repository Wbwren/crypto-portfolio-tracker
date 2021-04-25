import os
import nomics
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
if os.path.exists('env.py'):
    import env

app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

api_key = os.environ.get("NOMICS_API_KEY")
nomics = nomics.Nomics(api_key)

# Function to get current prices of coins
def get_price(*argv):
  coin_list = nomics.get_prices()
  selected_coins = []
  for arg in argv:
    for coin in coin_list:
      if coin['currency'] == arg:
        selected_coins.append(coin)
  return selected_coins


print(get_price('BTC', 'ETH', 'XMR'))

@app.route('/')
def test():
    return 'Hello World'


if __name__ == '__main__':
    app.run(host=os.environ.get('IP'), 
            port=int(os.environ.get('PORT')),
            debug=True)