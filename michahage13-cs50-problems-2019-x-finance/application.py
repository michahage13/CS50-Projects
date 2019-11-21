import os
import datetime

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
    """Show portfolio of stocks"""

    # select all of users purchases from history database table
    stocks = db.execute("SELECT symbol, SUM(shares), company, price FROM history WHERE id = :id GROUP BY symbol", id = session["user_id"])

    # look up each stock's current price and update price, initialize totalvalue (stocks value plus cash)
    totalvalue = 0
    for stock in stocks:
        temp = lookup(stock["symbol"])
        stock["price"] = temp["price"]
        totalvalue += (temp["price"] * stock["SUM(shares)"])

    cashtotals = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

    cashtotal = cashtotals[0]["cash"]

    return render_template("index.html", stocks = stocks, cashtotal = cashtotal, totalvalue = totalvalue)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # if user reaches site through POST (by submitting the form)
    if request.method == "POST":

        # check user for user input
        if not request.form.get("symbol"):
            return apology("Missing Symbol!", 400)
        elif not request.form.get("shares"):
            return apology("Missing Shares!", 400)

        # initialize variables for quote and check it
        quote = lookup(request.form.get("symbol"))

        # check if lookup was succesful
        if not quote:
            return apology("Enter valid symbol")

        # current cash of user from database and number of shares
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        shares = request.form.get("shares")

        # Check if user input is positive integer
        if not shares.isdigit():
            return apology("Enter a valid shares number")

        # change into integer variable and calculate total price
        shares = int(shares)
        totalsum = quote["price"] * shares

        # check if user can afford stocks
        if totalsum > cash[0]["cash"] :
            return apology("You can't afford this stock you broke loser")

        # update cash of user after purchase subtracting price multiplied by number of shares (totalsum)
        db.execute("UPDATE users SET cash = cash - :totalsum WHERE id = :id", totalsum = totalsum, id = session["user_id"])

        # update purchase history database
        db.execute("INSERT INTO history (id , symbol, shares, price, date, company) VALUES (:id, :symbol, :shares, :price, :timedate, :company)",
                    id = session["user_id"], symbol = quote["symbol"], shares = shares, price = quote["price"], timedate = datetime.datetime.now(), company=quote["name"])

        return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    # get username from form
    username = request.args.get("username")
    print(username)

    # check database for username
    checkname = db.execute("SELECT * FROM users WHERE username = :username", username=username)
    print(checkname)

    # if database returns something aka finds username
    if len(checkname) > 0:
        return jsonify(False)

    else:
        return jsonify(True)




@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # select all of users purchases from history database table
    stocks = db.execute("SELECT symbol, shares, date, price FROM history WHERE id = :id", id = session["user_id"])
    return render_template("history.html", stocks = stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via GET (as by reaching it through the Navbar)
    if request.method == "GET":
        return render_template("quote.html")

    elif request.method == "POST":
        quote = lookup(request.form["symbol"])
        if quote is None:
            return apology("Invalid symbol")

        return render_template("quoted.html", quote = quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
     # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password idiot", 400)

        # Ensure password and password confirmation match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match, please try again", 400)

        # hash password
        pwhash = generate_password_hash(request.form.get("password"))

         # get username from form
        username = request.form.get("username")

         # check database for username
        checkname = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        if len(checkname) > 0:
            print("username is taken")
            return apology("username is taken!", 400)

        # add user to database
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :pwhash)", username=request.form.get("username"), pwhash=pwhash)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Remember which user has logged in and log in after registration
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reaches register page by clicking on link
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method=="POST":
        #check user for user input
        if not request.form.get("symbol"):
            return apology("Missing Symbol!")
        elif not request.form.get("shares"):
            return apology("Missing Shares!")

        # initialize variables for quote, current cash of user from database and number of shares
        quote = lookup(request.form.get("symbol"))
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        shares = -abs(int(request.form.get("shares")))
        owned = db.execute("SELECT SUM(shares) AS sharenumber FROM history WHERE id = :id AND symbol = :symbol GROUP BY symbol", id = session["user_id"], symbol = request.form.get("symbol"))

        #check if user input is not bigger than available shares
        if abs(shares) > abs(owned[0]["sharenumber"]):
            return apology("You don't have enough stocks to sell!")
        totalsum = -abs(quote["price"] * shares)

        #update database, save as negative purchase
        db.execute("UPDATE users SET cash = cash - :totalsum WHERE id = :id", totalsum = totalsum, id = session["user_id"])

        # update purchase history database
        db.execute("INSERT INTO history (id , symbol, shares, price, date, company) VALUES (:id, :symbol, :shares, :price, :timedate, :company)",
                    id = session["user_id"], symbol = quote["symbol"], shares = shares, price = quote["price"], timedate = datetime.datetime.now(), company=quote["name"])


        return redirect("/")

    #get users symbols which he can sell
    else:
        stocks = db.execute("SELECT symbol, SUM(shares) FROM history WHERE id = :id GROUP BY symbol", id = session["user_id"])
        return render_template("sell.html", stocks = stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
