import os
# from dns.query import _set_selector_class
import nomics
import environ
import time
from flask import (
    Flask, flash, render_template, json,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from csv import reader
from bson.objectid import ObjectId


from werkzeug.security import generate_password_hash, check_password_hash

env = environ.Env()
environ.Env.read_env()

app = Flask(__name__)

app.config['MONGO_DBNAME'] = env('MONGO_DBNAME')
app.config['MONGO_URI'] = env('MONGO_URI')
app.secret_key = env('SECRET_KEY')

mongo = PyMongo(app)

api_key = env('NOMICS_API_KEY')
nomics = nomics.Nomics(api_key)


@app.route('/')
@app.route('/home')
def home():
    """ Return home view if user not in the session or redirect to dashboard
    """
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('base.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """ Registration functionality """
    if request.method == 'POST':
        # check if username already exists in db
        existing_user = mongo.db.users.find_one(
            {'username': request.form.get('username').lower()})

        if existing_user:
            flash('Username already exists')
            return redirect(url_for('register'))

        register = {
            'username': request.form.get('username').lower(),
            'password': generate_password_hash(request.form.get('password'))
        }
        mongo.db.users.insert_one(register)

        # put the new user into 'session' cookie
        session['user'] = request.form.get('username').lower()
        flash('Registration Successful!')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """ Login functionality """
    if request.method == 'POST':
        # check if username exists in db
        existing_user = mongo.db.users.find_one(
            {'username': request.form.get('username').lower()})

        if existing_user:
            # ensure hashed password matches user input
            if check_password_hash(
                    existing_user['password'], request.form.get('password')):
                session['user'] = request.form.get('username').lower()
                return redirect(url_for('dashboard'))
            else:
                # invalid password match
                flash('Incorrect Username and/or Password')
                return redirect(url_for('login'))

        else:
            # username doesn't exist
            flash('Incorrect Username and/or Password')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """ Forgot password page - functionality not currently implemented """
    if 'user' in session:
        return redirect(url_for('dashboard'))

    return render_template('forgot_password.html')


@app.route('/logout')
def logout():
    # remove user from session cookie
    session.pop('user')
    flash('You have been logged out')
    return redirect(url_for('login'))


def get_price(coins_purchased):
    coins_string = ""
    for k, v in coins_purchased.items():
        coins_string += k.upper() + ","
    coins_string = coins_string[:-1]
    return nomics.Currencies.get_currencies(coins_string)


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    def update_balance(user_coin_list):
        balance = 0

        if len(user_coin_list) < 1:
            return balance

        try:
            nomics_coins = get_price(user_coin_list)
            prices = {}
            for coin in nomics_coins:
                prices[coin['id']] = coin['price']
            i = 0
            for k, v in user_coin_list.items():
                balance += user_coin_list[k] * float(prices[k])
                i += 1
        except:
            flash('Failed to retrieve live prices for some symbols')
        return balance

    # Read the symbols from the csv file and store
    # in array to be passed to webpage
    list_of_coins = []
    with open('ticker_symbols.csv', 'r', encoding='utf-8') as symbols:
        # pass the file object to reader() to get the reader object
        csv_reader = reader(symbols)
        # Iterate over each row in the csv using reader object
        for row in csv_reader:
            # row variable is a list that represents a row in csv
            list_of_coins.append(row[0])

    def get_total_cost():
        transactions = mongo.db.transactions.find({'user': session['user']})
        total_cost = 0

        for transaction in transactions:
            if transaction['transactionType'] == 'buy':
                total_cost += transaction['cost']
            elif transaction['transactionType'] == 'sell':
                total_cost -= transaction['cost']
        return total_cost

    def get_user_coin_list():
        user_coin_list = {}

        transactions = mongo.db.transactions.find({'user': session['user']})
        for transaction in transactions:
            if transaction['transactionType'] == 'buy':
                if transaction['coin'] not in user_coin_list:
                    user_coin_list[transaction['coin']] = float(
                        transaction['quantity'])
                else:
                    for k, v in user_coin_list.items():
                        if k == transaction['coin']:
                            user_coin_list[k] += float(transaction['quantity'])
                            break
            else:
                if transaction['coin'] in user_coin_list:
                    for k, v in user_coin_list.items():
                        if k == transaction['coin']:
                            user_coin_list[k] -= float(transaction['quantity'])
                            break
        return user_coin_list

    if request.method == 'POST':
        selected_coin = request.form.get('coin').upper()
        if selected_coin not in list_of_coins:
            flash("Sorry, the coin entered is not currently supported")
        else:
            transaction = {
                'user': session['user'],
                'coin': selected_coin,
                'transactionType': request.form.get('transactionType'),
                'quantity': float(request.form.get('quantity')),
                'cost': float(request.form.get('cost'))
            }
            mongo.db.transactions.insert_one(transaction)
            # delay API call as limited to one call per second
            time.sleep(1)
            flash('Transaction Successfully Saved')

    user_coin_list = get_user_coin_list()
    balance = update_balance(user_coin_list)
    cost = get_total_cost()
    profit_loss = balance - cost

    return render_template('dashboard.html', balance=balance,
                           cost=cost, profit_loss=profit_loss,
                           user_coin_list=user_coin_list,
                           list_of_coins=list_of_coins)


@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user' not in session:
        return redirect(url_for('login'))

    transactions = mongo.db.transactions.find({'user': session['user']})

    transactions_list = []
    for transaction in transactions:
        transaction.pop('user')
        transactions_list.append(transaction)
    return render_template('transactions.html', transactions=transactions_list)


@app.route('/delete/<transaction>', methods=['GET', 'POST'])
def transaction_delete(transaction):
    if 'user' not in session:
        return redirect(url_for('login'))
    try:
        mongo.db.transactions.delete_one({"_id": ObjectId(transaction)})
    except:
        flash('Failed to delete transaction')
    return redirect(url_for('transactions'))


@app.route('/edit/<transaction>', methods=['GET', 'POST'])
def transaction_edit(transaction):
    if 'user' not in session:
        return redirect(url_for('login'))

    list_of_coins = []
    with open('ticker_symbols.csv', 'r', encoding='utf-8') as symbols:
        # pass the file object to reader() to get the reader object
        csv_reader = reader(symbols)
        # Iterate over each row in the csv using reader object
        for row in csv_reader:
            # row variable is a list that represents a row in csv
            list_of_coins.append(row[0])

    if request.method == 'POST':
        try:
            selected_coin = request.form.get('coin').upper()
            if selected_coin not in list_of_coins:
                flash("Sorry, the coin entered is not currently supported")
            else:
                mongo.db.transactions.replace_one(
                    {"_id": ObjectId(transaction)},
                    {'user': session['user'],
                     'coin': selected_coin,
                     'transactionType': request.form.get('transactionType'),
                     'quantity': float(request.form.get('quantity')),
                     'cost': float(request.form.get('cost'))}
                )
                flash('Transaction Successfully Saved')
                return redirect(url_for('transactions'))
        except:
            flash('Failed to update transaction')
    return render_template('edit_transaction.html',
                           list_of_coins=list_of_coins)


if __name__ == '__main__':
    app.run(host=env('IP'),
            port=int(env('PORT')),
            debug=False)
