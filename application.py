import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # Select the user and manipulate their data
    results = db.execute("SELECT * FROM transactions WHERE user = :user",user = session["user_id"])

    # Select their current cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id",id = session["user_id"])
    stock_total = 0
    # Get their purchase history, check the current stock price of that symbol, number of shares and display through index.html
    for result in results:
        symbol = str(result['symbol'])
        shares = float(result['shares'])
        quote = lookup(symbol)
        current_price = float(quote['price'])
        name = str(quote['name'])
        result['name'] = name
        result['price'] = current_price
        total_value = shares * current_price
        result['totalPrice'] = total_value
        stock_total += total_value

    # Calculate the stock value + their current price
    grand_total = cash[0]['cash'] + stock_total
    return render_template("index.html",results = results,cash=cash[0]['cash'],grand_total = grand_total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
# Implement render-template and rest
def buy():
    if(request.method == "POST"):
        # Look up the symbols, and the shares user want to buy
        symbols = request.form.get("symbol")
        number_of_shares = request.form.get("shares")
        quote = lookup(symbols)
        #Check if any of the fields are empty of shares is less than 1
        if not symbols:
            return apology("Need to fill out the symbol")
        elif not number_of_shares:
            return apology("Need to fill out the shares")
        elif float(number_of_shares) < 1 :
            return apology("Shares must be a positive integer")
        elif symbols.isnumeric():
            return apology("Symbols doesn't exist")
        #Check if the user can afford the total price of amount of shares
        cash =  db.execute("SELECT cash from users WHERE id = :id ",id = session["user_id"])
        prices = quote['price']
        total_price = float(number_of_shares) * float(prices)
        list_symbol = []
        user_shares = db.execute("SELECT shares FROM transactions WHERE user = :id AND symbol = :symbol",id = session['user_id'],symbol = symbols)
        if cash[0]['cash'] >= total_price:

            # Check if they already have that type of shares in their stocks, if yes, then update, else insert new shares into the stock
            if not user_shares:
                db.execute("INSERT INTO transactions (symbol,price,shares,total,user)VALUES(:symbol,:price,:shares,:total,:user)",symbol = symbols,price = prices,shares = number_of_shares,total = total_price,user=session["user_id"])
            else:
                db.execute("UPDATE transactions SET shares = shares + :shares,total = total + :total WHERE user = :user",shares = number_of_shares,total = total_price,user = session['user_id'])

            # Update the amount of cash after purchasing
            update = db.execute("UPDATE users SET cash = cash - :total WHERE id = :id",total = total_price,id= session["user_id"])
            return redirect("/")

        # Return apology if they don't have enough money
        else:
            return apology("Not enough money")
    elif(request.method == "GET"):
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    datas = db.execute("SELECT symbol,shares,history,price FROM transactions WHERE user = :user ",user = session['user_id'])
    return render_template("history.html",datas = datas)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # Check the submission
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

    # Check if the stock exist in the api
        if not quote:
            return apology("The stock doesn't exist")
        else:
            # Return the price, symbol, and name of that stock in the template quoted.html
            return render_template("quoted.html",name = quote['name'],symbol = quote['symbol'],prices = quote['price'])

    # Display the input for symbol
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # If the user is submitting through form, it will insert data into databases
    if(request.method == "POST" ):

        # Get the value that is going to be submmitted in the register.html
        usernames = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Test if username,password,confirmation is empty. Also test if the password match the confirmation
        if not usernames:
            return apology("username need to be fill out")
        elif not password:
            return apology("password need to be fill out")
        elif not confirmation:
            return apology("confirmation need to be fill out")
        elif not password == confirmation:
            return apology("password and confirmation doesn't match")
        # hash the  password into hashes and insert username/passwords into the databases
        hashValue = generate_password_hash(password,method = "sha256")
        results = db.execute("INSERT INTO users (username,hash)VALUES(:username, :hash)",username = usernames ,hash=hashValue)

        # Check if username already exist in the database.
        if not results:
            return apology("username existed")

        #If everything success, redirect to the home page
        return redirect("/")

    # Display the form in register.html
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    results = db.execute("SELECT * FROM transactions WHERE user = :user",user = session["user_id"])
    if(request.method == "POST"):
        # Get the data from sell.html form
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Check if they missing any fields
        if not shares:
            return apology("Missing shares")
        if not symbol:
            return apology("Missing symbol")
        shares = int(shares)
        symbol = str(symbol)

        # Look up the current price and it's value
        quote = lookup(symbol)
        price = quote['price']
        total_value = float(price) * float(shares)

        # Check if they have enough shares in stock to sell
        for data in results:
            if shares > data['shares']:
                return apology("Not enough shares")

        # Update the amount of shares in the database after selling
        update = db.execute("UPDATE transactions SET shares = shares - :shares WHERE user = :user AND symbol = :symbol",shares = shares,user = session['user_id'],symbol = symbol)

        # Update the amount of cash of that user
        update_cash = db.execute("UPDATE users SET cash = cash + :total_value WHERE id = :id",total_value = total_value, id = session['user_id'])
        select_shares = db.execute("SELECT * from transactions WHERE user = :user AND shares = 0",user = session['user_id'])

        # Delete their data if they have no more shares
        for data in select_shares:
            if data['shares'] == 0:
                delte_shares = db.execute("DELETE from transactions WHERE user = :user AND shares = 0", user = session['user_id'])
        return redirect("/")
    else:
        # Display responsive symbol input fields and remove duplicates
        results = db.execute("SELECT * FROM transactions WHERE user = :user",user = session["user_id"])
        final = []
        for data in results:
            symbols = str(data['symbol'])
            if symbols not in final:
                final.append(symbols)
        return render_template("sell.html",final = final)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
