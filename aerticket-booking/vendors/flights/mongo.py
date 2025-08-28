import os
from pymongo import MongoClient
from dotenv import load_dotenv

class MongoHandler:
    def __init__(self):
        # Load environment variables from the .env file
        load_dotenv()

        # Get MongoDB connection details from environment variables
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        database = os.getenv('MONGO_DATABASE', 'project')
        collection = 'searches'

        # Initialize the MongoDB client
        self.client = MongoClient(mongo_uri)
        self.db = self.client[database]
        self.collection = self.db[collection]

    def insert_one(self, document):
        """Insert a single document into the collection."""
        return self.collection.insert_one(document)

    def find_one(self, query):
        """Find a single document in the collection."""
        return self.collection.find_one(query)

    def find(self, query):
        """Find multiple documents in the collection."""
        return self.collection.find(query)

    def update_one(self, query, update):
        """Update a single document in the collection."""
        return self.collection.update_one(query, update)

    def delete_one(self, query):
        """Delete a single document in the collection."""
        return self.collection.delete_one(query)

    def delete_many(self, query):
        """Delete multiple documents in the collection."""
        return self.collection.delete_many(query)

    def count_documents(self, query):
        """Count the number of documents matching a query."""
        return self.collection.count_documents(query)
