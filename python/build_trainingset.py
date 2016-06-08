#!/usr/bin/env python

### imports ###

from __future__ import print_function
import sys
import json
import pymongo
import random
import argparse
import dataIO
from config import c as config

### constants ###

# DB_FILE = config["sqlite3"]["db_file"]
# MONGO_DB = config["mongodb"]["database"]
# COLLECTIONS = config["mongodb"]["collections"]

### functions ###

# recursion depth limit errors at larger set_length sizes
# def randomSetRec(total, set_len, x=set()):
#   y = random.randrange(0, total)
#   x.add(y)
#   if len(x) < set_len:
#     randomSetRec(total, set_len, x=x)
#   return x

# used to build method below
# def randomSetWhile(total, set_len):
#   x=set()
#   while len(x) < set_len:
#     y = random.randrange(1, total)
#     x.add(y)
#   return x

### classes ###

class TrainingSet(dataIO.MongoIO):
  def __init__(self, collection, target_field, fraction):
    # have to specifically call parent class init!?
    dataIO.MongoIO.__init__(self)
    self.collection = collection
    self.fraction = fraction
    self.int_list = None
    self.target_field = target_field
    self.training_set = []

  def _randomSetWhile(self):
    total_len = self.collection.count()
    set_len = total_len / self.fraction
    x = set()
    while len(x) < set_len:
      y = random.randrange(1, total_len)
      x.add(y)
    return x

  def build(self):
    ''' build the training set using a random sampling from total set'''
    # if the collection is just the name, then use name to open connection to actual collection
    if type(self.collection) == str:
      database = self.db
      target_db = self.client[database]
      self.collection = target_db[self.collection]
    self.training_set = []
    self.int_list = self._randomSetWhile()
    i = 1
    for record in self.collection.find():
      if i in self.int_list:
        # try-except cuz not all rss records have 'content' field
        try:
          self.training_set.append(record[self.target_field])
        except KeyError:
          pass
      i += 1
    ts_len = len(self.training_set)
    ideal_ts_len = len(self.int_list)
    tot_len = self.collection.count()
    print("Training set: %s, Expected: %s, Collection size: %s" % (ts_len, ideal_ts_len, tot_len), file=sys.stdout)
    print("Fraction of Expected: %s" % (ts_len / float(ideal_ts_len)), file=sys.stdout)
    print("Fraction of total: %s" % (ts_len / float(tot_len)), file=sys.stdout)

  def writeFile(self, out_file):
    with open(out_file, "w") as out:
      for record in self.training_set:
        # getting NoneType errors from some rss records... have 'content', but is empty?
        if record is not None:
          out.write(record.encode('utf8') + "\n")

### main ###

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("collection", choices=dataIO.COLLECTIONS, help="specify target collection from which to build set")
  parser.add_argument("-o", "--out", metavar="FILE", dest="out_file", default=None,
                    help="Specify the output FILE.", required=True)
  parser.add_argument("-d", "--denom", metavar="INT", dest="denom", default=10, type=int,
                    help="Denominator for slicing collection. Default is 10 == x/10 to produce set")
  args = parser.parse_args()

  target_collection = args.collection
  out_file = args.out_file
  denom = args.denom

  # handle different field names for each collection
  if target_collection == "twitter":
    target_field = "text"
  if target_collection == "rss":
    target_field = "description"
    # Feb 2016: For now, not all data points have "content", and the scraping looks to have
    # a reasonable amount of flotsum; "description" is a cleaner dataset at this point,
    # though maybe not as useful in the long run
    # target_field = "content"

  ts = TrainingSet(target_collection, target_field, denom)
  ts.build()
  ts.writeFile(out_file)


