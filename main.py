import redis
import ast
from flask import Flask, request

app = Flask(__name__)
r = redis.StrictRedis("localhost", 6379, charset="utf-8", decode_responses=True)


def int_check(ussd_string):
    try:
        float(ussd_string)
        return True
    except ValueError:
        return False


@app.post("/ussd")
def ussd():
    session_id = request.values.get("sessionId", None)
    service_code = request.values.get("serviceCode", None)
    phone_number = request.values.get("phoneNumber", None)
    ussd_string = str(request.values.get("text", "default"))
    session = r.hgetall(session_id)
    current_screen = "main_menu"
    print(session)
    if session:
        current_screen = session["current_screen"]
    if ussd_string == "0":
        current_screen = session["previous_screen"]
        ussd_string = session["previous_choice"]
    if ussd_string == "00":
        current_screen = "main_menu"
    if current_screen == "main_menu":
        customer_data = r.hgetall(phone_number)
        if not customer_data:
            customer_data = {
                "customer_balance": "1000",
                "says_balance": "0",
                "opt_in": "0",
            }
            r.hmset(
                phone_number,
                {"customer_balance": 10000, "says_balance": 0, "opt_in": "0"},
            )
        customer_data = ast.literal_eval(str(customer_data))
        response = f"Welcome back to SAYS. Current wallet balance: Ksh.{int(float(customer_data['customer_balance']))}\nCurrent SAYS balance: Ksh.{int(float(customer_data['says_balance']))}\n1. Pay"
        if customer_data["opt_in"] == "1":
            response += "\n2. Change SAYS percentage"
        else:
            response += "\n2. Opt in to SAYS"
        r.hmset(
            session_id,
            {
                "customer_data": str(customer_data),
                "current_screen": "menu_start",
                "previous_screen": "main_menu",
            },
        )

    elif current_screen == "menu_start":
        if ussd_string == "1":
            response = "CON Please enter the number you'd like to pay to:"
            r.hmset(
                session_id,
                {
                    "current_screen": "payment_start",
                    "previous_screen": current_screen,
                    "previous_choice": ussd_string,
                },
            )
        elif ussd_string == "2":
            customer_data = r.hgetall(phone_number)
            customer_data = ast.literal_eval(str(customer_data))
            if customer_data["opt_in"] == "1":
                response = f"CON Current percentage {float(customer_data['opt_in_percent']) * 100}%. How much would you like to edit it to?"
            else:
                response = "CON How much do you want to be saving per transaction? (Percentage):"
            r.hmset(
                session_id,
                {
                    "current_screen": "opt_in",
                    "previous_screen": current_screen,
                    "previous_choice": ussd_string,
                },
            )
    elif current_screen == "payment_start":
        if len(ussd_string) != 10 and len(ussd_string) != 12:
            response = "CON Invalid number added, kindly ensure that it starts with 07 or 254. Please try again:"
        else:
            response = "CON Enter amount you would like to pay:"
            r.hmset(
                session_id,
                {
                    "current_screen": "payment_continue",
                    "previous_screen": current_screen,
                    "previous_choice": ussd_string,
                    "number_to": ussd_string,
                },
            )
    elif current_screen == "payment_continue":
        customer_data = r.hgetall(phone_number)
        customer_data = ast.literal_eval(str(customer_data))
        if int_check(ussd_string):
            if int(ussd_string) > float(customer_data["customer_balance"]):
                response = f"CON Amount input is greater than the amount in your wallet. Kindly ensure it is less than Ksh. {customer_data['customer_balance']}:"
                next_screen = 'payment_continue'
            else:
                if customer_data["opt_in"] == "0" or customer_data["opt_in"] == "2":
                    response = "CON Would you be interested in signing up to SAYS, where you save money as you spend it?\n1. Yes\n2. Remind me Later\n3. No thanks"
                    next_screen = "opt_in_choice"
                else:
                    opt_in_percent = 0
                    if 'opt_in_percent' in customer_data:
                        opt_in_percent = customer_data["opt_in_percent"]
                    if (float(ussd_string) + (float(ussd_string) * float(
                        opt_in_percent)) > float(customer_data["customer_balance"])):
                        response = f"CON Amount input is greater than the amount in your wallet plus your SAYS percentage. Kindly ensure it is less than Ksh. {float(customer_data['customer_balance']) + float(customer_data['says_balance'])}:"
                        next_screen = "payment_continue"
                    else:
                        response = f"CON Confirm details.\nNumber to: {session['number_to']}\nAmount: {ussd_string}\n1. Confirm"
                        next_screen = "payment_confirm"
                r.hmset(
                    session_id,
                    {
                        "current_screen": next_screen,
                        "previous_screen": current_screen,
                        "previous_choice": ussd_string,
                        "amount": ussd_string,
                    },
                )
        else:
            response = "CON Invalid amount input. Kindly ensure that it is a number. Kindly try again:"
    elif current_screen == "opt_in_choice":
        if ussd_string == "1":
            response = (
                "CON How much do you want to be saving per transaction? (Percentage):"
            )
            opt_in = 1
            next_screen = "opt_in_payment"
        else:
            if ussd_string == "2":
                opt_in = 2
            else:
                opt_in = 3
            response = f"CON You can change this choice in the main menu.\nConfirm details.\nNumber to: {session['number_to']}\nAmount: {session['amount']}\n1. Confirm"
            next_screen = "payment_confirm"
        r.hmset(
            session_id,
            {
                "current_screen": next_screen,
                "previous_screen": current_screen,
                "previous_choice": ussd_string,
            },
        )
        r.hmset(
            phone_number,
            {"opt_in": opt_in},
        )
    elif current_screen == "opt_in_payment":
        response = f"CON You are now saving {ussd_string}% per transaction. This can be changed in the main menu.\nConfirm transaction details.\nNumber to: {session['number_to']}\nAmount: {session['amount']}\n1. Confirm"
        r.hmset(
            session_id,
            {
                "current_screen": "payment_confirm",
                "previous_screen": current_screen,
                "previous_choice": ussd_string,
            },
        )
        r.hmset(
            phone_number,
            {"opt_in_percent": float(ussd_string) / 100},
        )
    elif current_screen == "payment_confirm":
        if ussd_string == "1":
            customer_data = r.hgetall(phone_number)
            customer_data = ast.literal_eval(str(customer_data))
            says_balance = 0
            if customer_data['opt_in'] == '1':
                says_balance = float(session["amount"]) * float(
                    customer_data["opt_in_percent"]
                )
            new_balance = (
                float(customer_data["customer_balance"])
                - float(session["amount"])
                - says_balance
            )
            new_says_balance = float(customer_data["says_balance"]) + says_balance
            response = "CON Successfully transacted. Do you want to transact again?\n1. Confirm"
            r.hmset(
                phone_number,
                {"customer_balance": new_balance, "says_balance": new_says_balance},
            )
            r.hmset(
                session_id,
                {
                    "current_screen": "menu_start",
                    "previous_screen": current_screen,
                    "previous_choice": ussd_string,
                },
            )
    elif current_screen == "opt_in":
        response = f"CON Are you sure you want to use {ussd_string}% as your new SAYS percentage?\n1. Confirm"
        r.hmset(
            session_id,
            {
                "current_screen": "opt_in_confirm",
                "previous_screen": current_screen,
                "previous_choice": ussd_string,
                "opt_in_percent": ussd_string,
            },
        )
    elif current_screen == "opt_in_confirm":
        response = f"CON Changed to {session['opt_in_percent']}%. Would you like to transact now?\n1. Transact"
        r.hmset(
            session_id,
            {
                "current_screen": "menu_start",
                "previous_screen": current_screen,
                "previous_choice": ussd_string,
            },
        )
        r.hmset(
            phone_number,
            {"opt_in_percent": int(session["opt_in_percent"]) / 100, "opt_in": 1},
        )
    else:
        response = "CON Invalid choice. Please try again."
    return response


if __name__ == "__main__":
    app.run(debug=True)
