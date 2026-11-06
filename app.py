from datetime import timedelta
from flask import Flask, render_template, request, redirect, session, flash
from db import validate_pin, get_account, withdraw, get_history

app = Flask(__name__)
app.secret_key = "replace-this-with-a-long-random-string"
app.permanent_session_lifetime = timedelta(seconds=60)  # NFR1 session timeout

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        card = request.form.get("card_number", "").strip()
        pin = request.form.get("pin", "").strip()
        ok, msg, card_row = validate_pin(card, pin)
        if ok:
            session.permanent = True
            session["account_id"] = card_row["account_id"]
            return redirect("/menu")
        flash(msg, "error")
    return render_template("login.html")

@app.route("/menu")
def menu():
    if "account_id" not in session:
        return redirect("/")
    return render_template("menu.html")

@app.route("/balance")
def balance():
    if "account_id" not in session:
        return redirect("/")
    acc = get_account(session["account_id"])
    return render_template("balance.html", balance=acc["balance"])

@app.route("/withdraw", methods=["GET", "POST"])
def withdraw_route():
    if "account_id" not in session:
        return redirect("/")
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            flash("Invalid amount", "error")
            return redirect("/withdraw")
        ok, msg = withdraw(session["account_id"], amount)
        flash(msg, "success" if ok else "error")
        return redirect("/withdraw")
    return render_template("withdraw.html")

@app.route("/history")
def history():
    if "account_id" not in session:
        return redirect("/")
    rows = get_history(session["account_id"])
    return render_template("history.html", rows=rows)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)