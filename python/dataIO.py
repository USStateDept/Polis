#!/usr/bin/env python

### import ###

from __future__ import print_function
import sys
import json
from datetime import datetime
import csv
# import sys
# import argparse
# import os.path
# import re
# import uuid
import sqlite3
# import pymongo
import codecs
from config import c as config

try:
  import pymongo
except ImportError:
  print("Warning: pymongo not imported")

### constants ###

DB_FILE = config["sqlite3"]["db_file"]
MONGO_DB = config["mongodb"]["database"]
COLLECTIONS = config["mongodb"]["collections"]

### functions ###

### classes ###

class FileIO:
  '''
  General read/write of files
  '''
  def __init__(self, file_name=None, data=None):
    self.file = file_name
    # self.fields = []
    self.data = data

  def write(self):
    with codecs.open(self.file, "w", "utf-8") as f:
      for line in self.data:
        # f.write(line + u"\n")
        f.write(line)
  
  def read(self):
    with codecs.open(self.file, "r", "utf-8") as f:
      li = []
      for line in f.readlines():
        li.append(line)
      self.data = li

class SQLio:
  '''
  Handles connection (reads, mostely) to SQL DB that governs the entity relationships, 
  i.e. Mayor of Portland separates "Mayor" (person) from "Portland" (city)
  '''
  def __init__(self, db_file=DB_FILE):
    self.db = db_file
    self.conn = None
    self.cur = None
  
  def connect(self):
    self.conn = sqlite3.connect(self.db)
    self.cur = self.conn.cursor()

class MongoIO:
  def __init__(self, collections=COLLECTIONS, m_db=MONGO_DB):
    self.client = pymongo.MongoClient()
    self.m_db = m_db
    self.collection = None
    self.collections = collections

  def matchExisting(self, collection, id_field, record_id):
    '''
    Determines if a record has already been inserted into the database
    Returns True if 
    '''
    database = self.m_db
    target_db = self.client[database]
    if collection in self.collections:
      target_collection = target_db[collection]
      if target_collection.find({id_field: record_id}).count() == 0:
        return True
      elif target_collection.find({id_field: record_id}).count() == 1:
        return False
      else:
        print("warn about multiple insertions of a record")
        return False

  def set_collection(self, collection=None):
    try:
      assert collection in self.collections
      self.collection = collection
    except AssertionError:
      print("specified collection is not in %s" % str(self.collections), file=sys.stderr)

  def writeRecord(self, collection, record):
    '''
    Generalized method to write a record into a specific collection
    Need to update to use self.collection
    '''
    database = self.m_db
    # use bracket notation otherwise .database, etc. are interpreted LITERALLY by MongoDB
    target_db = self.client[database]
    if collection in self.collections:
      target_collection = target_db[collection]
      record_id = target_collection.insert_one(record).inserted_id
      log_info = (str(record_id), collection)
      log_msg = "INFO: %s was inserted into %s" % log_info
      print(log_msg, file=sys.stdout)

### main ###
if __name__ == "__main__":
  # Not implemented
  pass