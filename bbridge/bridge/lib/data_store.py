
from flask import Flask
from flask_peewee.rest import RestAPI
from peewee import Model, FloatField, DateTimeField, SqliteDatabase

db = SqliteDatabase('store.db')

class DataStore():

    def __init__(self):
        # Initialize flask
        self.flask = Flask('data_store')
        self.api = RestAPI(self.flask)

    def register(self, model):
        self.api.register(model)
        # Configure the URLs
        self.api.setup()


class DataModel(Model):

    timestamp = DateTimeField()

    class Meta:
        database = db


