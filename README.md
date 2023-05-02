# Distributed Banking System using MongoDB and Kafka

## Project structure

```
Load Balancer: Flask Limiter & Kafka
Message Bus: Kafka
Banking Server: MongoDB
---Banking Server 1: 
--------MongoDB collection: BankingServer
---Banking Server 2: 
--------MongoDB collection: BankingServerBackup


Main Language: Python
REST api: Flask
Back-end: pymongo
Authorization: flask_jwt_extended
Encryption: cryptography
```

## Quick Start

### Install the requirement

```shell
pip install -r requirements.txt
```

Back-end requirement

`Zookeeper` -- for Kafka using

`Kafka` -- as message bus

`MongoDB` -- as database

### Setup server

Change the `URI` and `Kafka Server`in the start of `MessageBus.py` and `Server.py` to your own server path

Especially for `Kafka`, you have to set the `topic` and related parameter as your local setting

### Start 

Start both `Server.py` and `MessageBus.py` in different thread

```shell
python Server.py
python MessageBus.py
```

### Using

`BankingServer.postman_collection.json` is for **postman** and you can import that file to get all the request for testing

Request List:

* Get account by accountId
* Create new account
* Create new credit
* Create new debits
* Get transaction by accountId
* Get transaction by accountId ( filtering with type)
* register -- for authorized visiting
* login -- for authorized visiting

**Caution**: You have to first `register` and `login` to get token for authorized visiting

> **Suggestion**: Most of the `POST` operation returns an OK message so that you may have to install `MongoDBCompass` to see the back-end change clearly.