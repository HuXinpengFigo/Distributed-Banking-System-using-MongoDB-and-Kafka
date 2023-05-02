# -*- coding: utf-8 -*-
from flask import Flask
from flask import jsonify
from flask import request
from flask_jwt_extended import JWTManager, jwt_required, create_access_token

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from pymongo import MongoClient
from kafka import KafkaProducer

from cryptography.fernet import Fernet

from datetime import datetime
import json
from bson import json_util

app = Flask(__name__)
jwt = JWTManager(app)
limiter = Limiter(get_remote_address, app=app)

# JWT Config
app.config["JWT_SECRET_KEY"] = "for-osl-tech-test"

MONGO_URI = "mongodb://localhost:27017"
KFK_URI = "10.6.88.250:9092"

# For currency validation
valid_currency = [
    "USD",
    "BTC",
    "EUR",
    "ETH",
    "HKD"
]


# Avoid BSON problem
def get_data(data):
    data['_id'] = str(data['_id'])
    return data


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/register", methods=["POST"])
def register():
    client = MongoClient(MONGO_URI)
    user = client.BankingServer.User
    user_backup = client.BankingServerBackup.User

    email = request.form["email"]
    test = user.find_one({"email": email})
    if test:
        return jsonify(message="User Already Exist"), 409
    else:
        password = request.form["password"]
        user_info = dict(email=email, password=password)
        user.insert_one(user_info)
        user_backup.insert_one(user_info)
        return jsonify(message="User added sucessfully"), 201


@app.route("/login", methods=["POST"])
def login():
    client = MongoClient(MONGO_URI)
    user = client.BankingServer.User

    if request.is_json:
        email = request.json["email"]
        password = request.json["password"]
    else:
        email = request.form["email"]
        password = request.form["password"]

    test = user.find_one({"email": email, "password": password})
    if test:
        access_token = create_access_token(identity=email)
        return jsonify(message="Login Succeeded!", access_token=access_token), 201
    else:
        return jsonify(message="Bad Email or Password"), 401


@app.route("/accounts", methods=['GET'])
@jwt_required()
@limiter.limit("10/second")  # To test, change it to 1/minute and try twice
def get_accounts_info_via_account_id():
    account_id = str(request.args.get('accountId'))

    # Validate of URL in account_id
    if not account_id.isnumeric():
        return "Invalid URL"

    client = MongoClient(MONGO_URI)

    # Get account details from mongodb
    account_detail = client.BankingServer.Accounts.find_one({"account_id": account_id})

    # Validate the account
    if account_detail is None:
        return "Account does not exist"

    # For process mongodb data which _id cannot return as JSON directly
    temp = get_data(account_detail)

    return jsonify(temp)


@app.route("/accounts/<accountId>/transactions", methods=['GET'])
@jwt_required()
def get_transaction_info_via_account_id(accountId):
    client = MongoClient(MONGO_URI)

    # Validate of URL in account_id
    if not accountId.isnumeric():
        return "Invalid URL"

    # Get account details from mongodb
    transaction_detail = client.BankingServer.Transactions.find_one({"account_id": accountId})

    # Validate the account
    if transaction_detail is None:
        return "Account does not exist"

    # For process mongodb data which _id cannot return as JSON directly
    json_transaction = get_data(transaction_detail)

    # For transaction filtering
    if request.args.get("type") is None:
        return jsonify(json_transaction)
    else:
        filtered_transaction_frame = {
            "_id": json_transaction["_id"],
            "account_id": json_transaction["account_id"],
            "transactions": [],
        }
        for t in json_transaction["transactions"]:
            if t["type"] == request.args.get("type"):
                filtered_transaction_frame["transactions"].append(t)
        print(filtered_transaction_frame)

        return jsonify(filtered_transaction_frame)


@app.route("/accounts", methods=['POST'])
@jwt_required()
def create_new_account():
    account_json = request.json

    # Validate required fields
    if (account_json.get("account_type") is None or
            account_json.get("balance") is None or
            account_json.get("account_holder") is None or
            account_json.get("currency") is None):
        return "Required fields is losing"

    # Validate account_type, balance, account_holder, currency
    if account_json["account_type"] == "savings" or account_json["account_type"] == "checking":
        pass
    else:
        return "Invalid account_type"
    if float(account_json["balance"]) < 0.0:
        return "Invalid balance amount"
    if account_json["currency"] not in valid_currency:
        return "Invalid currency type"

    # Validate account_holder
    account_holder = account_json["account_holder"]
    if (account_holder.get("name") is None or
            account_holder.get("email") is None or
            account_holder.get("address") is None or
            account_holder.get("phone_number") is None):
        return "Invalid account_holder"

    # Give account id to new account (Can customize)
    account_id = "1234567899"
    account_details_frame = {
        "account_id": account_id,
        "account_type": account_json["account_type"],
        "balance": account_json["balance"],
        "account_holder": account_json["account_holder"],
        "created_at": datetime.now()
    }

    account_frame = {
        "operation": "create_account",
        "account_details": account_details_frame
    }

    producer = KafkaProducer(bootstrap_servers=[KFK_URI])
    future = producer.send('TestTopic', json.dumps(account_frame, default=json_util.default).encode('utf-8'))
    result = future.get(timeout=10)
    print(result)

    return "OK"


def encryption_for_transaction(data_to_encrypt):
    # Generate key and store it in key.key file every time when there a new transaction
    key = Fernet.generate_key()
    with open("key.key", "wb") as file:
        file.write(key)

    with open("key.key", "rb") as file:
        key = file.read()

    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(data_to_encrypt).encode("utf-8"))

    return encrypted


def process_of_transaction(transaction_type, account_id, transaction_json):
    # Encryption for transaction
    transaction_encrypted = encryption_for_transaction(transaction_json)

    transaction_frame = {
        "operation": transaction_type,
        "account_id": str(account_id),
        "transaction": transaction_encrypted.decode("utf-8")
    }

    producer = KafkaProducer(bootstrap_servers=[KFK_URI])
    future = producer.send('TestTopic', json.dumps(transaction_frame, default=json_util.default).encode('utf-8'))
    result = future.get(timeout=10)
    print(result)

    return "OK"


@app.route("/accounts/<accountId>/credits", methods=['POST'])
@jwt_required()
def create_new_credits(accountId):
    # Get the transaction json
    transaction_json = request.json

    # Validate account id existence
    client = MongoClient(MONGO_URI)
    if client.BankingServer.Accounts.find_one({"account_id": accountId}) is None:
        return "Account does not exist"

    # Validate required fields
    if (transaction_json.get("amount") is None or
            transaction_json.get("description") is None):
        return "Required fields is missing"

    # Validate amount
    if float(transaction_json["amount"]) < 0.0:
        return "Invalid amount"

    # Process with the transaction
    process_of_transaction("credits", accountId, transaction_json)

    return "OK"


@app.route("/accounts/<accountId>/debits", methods=['POST'])
@jwt_required()
def create_new_debits(accountId):
    # Get the transaction json
    transaction_json = request.json

    # Validate required fields
    if (transaction_json.get("amount") is None or
            transaction_json.get("description") is None):
        return "Required fields is missing"

    # Validate amount
    if float(transaction_json["amount"]) < 0.0:
        return "Invalid amount"

    # Process with the transaction
    process_of_transaction("debits", accountId, transaction_json)

    return "OK"


if __name__ == '__main__':
    app.run()
