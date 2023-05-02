# -*- coding: utf-8 -*-

from kafka import KafkaConsumer
from pymongo import MongoClient
import json
from cryptography.fernet import Fernet

URI = "mongodb://localhost:27017"
KFK_URI = "10.6.88.250:9092"

consumer = KafkaConsumer('TestTopic', bootstrap_servers=[KFK_URI])


# Avoid BSON problem
def get_data(data):
    data['_id'] = str(data['_id'])
    return data


def mongo_db_sinking_accounts_with_server(server, account_details):
    # Create new account
    result = server.Accounts.insert_one(account_details)
    print(result)

    # Create new transaction document with no transaction contents
    new_transaction_record = {
        "account_id": account_details["account_id"],
        "transactions": []
    }
    result = server.Transactions.insert_one(new_transaction_record)
    print(result)


def mongo_db_accounts_sinking(account_details):
    client = MongoClient(URI)
    
    # Sinking for main server
    mongo_db_sinking_accounts_with_server(client.BankingServer, account_details)
    # Sinking for backup server
    mongo_db_sinking_accounts_with_server(client.BankingServerBackup, account_details)

    return


def mongo_db_transaction_update_sinking_with_server(transaction_type, account_id, server, transaction):
    co_accounts = server.Accounts

    # Find if account_id exist
    account = co_accounts.find_one({"account_id": account_id})

    # Calculate the new balance after transaction
    if transaction_type == "credits":
        new_balance = account["balance"] + transaction["amount"]
    elif transaction_type == "debits" and account["balance"] - transaction["amount"] >= 0:
        new_balance = account["balance"] - transaction["amount"]
    else:
        print("No enough balance, fair to debit")
        return "No enough balance, fair to debit"

    # Update the balance after credit in Accounts
    query = {"account_id": account_id}
    new_value = {"$set": {"balance": new_balance}}
    server.Accounts.update_one(query, new_value)

    # Update the transaction content in Transactions
    new_transaction = {
        "transaction_id": "txn_123456",
        "description": transaction["description"],
        "amount": transaction["amount"],
        "type": transaction_type,
        "timestamp": "2023-03020T14::00:00:00Z"
    }
    query = {"account_id": account_id}
    new_value = {"$push": {"transactions": new_transaction}}
    server.Transactions.update_one(query, new_value)


def message_decrypt(transaction_to_decrypt):
    # Read key for decryption
    with open("key.key", "rb") as file:
        key = file.read()

    fernet = Fernet(key)
    decrypted = fernet.decrypt(transaction_to_decrypt)

    return json.loads(decrypted.decode("utf-8"))


def mongo_db_transaction_update_sinking(transaction_type, account_id, transaction):
    client = MongoClient(URI)

    # Decryption of transaction
    transaction_decrypted = message_decrypt(transaction.encode("utf-8"))

    mongo_db_transaction_update_sinking_with_server(transaction_type, account_id, client.BankingServer, transaction_decrypted)
    mongo_db_transaction_update_sinking_with_server(transaction_type, account_id, client.BankingServerBackup, transaction_decrypted)

    return


if __name__ == '__main__':
    for msg in consumer:
        # Get data from producer in JSON
        record = json.loads(msg.value)
        if record["operation"] == "create_account":
            print("Process of :", record["operation"])
            # print(record["account_details"])
            mongo_db_accounts_sinking(record["account_details"])

        if record["operation"] == "credits" or record["operation"] == "debits":
            print("Process of :", record["operation"])
            # print(record["account_id"])
            # print(record["transaction"])
            mongo_db_transaction_update_sinking(record["operation"], record["account_id"], record["transaction"])
