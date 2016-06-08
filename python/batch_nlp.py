#!/usr/bin/env python

##
## IMPORTS
##

from __future__ import print_function
# from copy import deepcopy
# import codecs
# import re
import nltk
import sys
import os
import glob
# import operator
# import random
import uuid
from shutil import copyfile
from datetime import datetime
from config import c as config
from dataIO import *
from nbayes_classify import *

##
## CONSTANTS and VARIABLES
##

## confidence metrics 

# fold above second highest score (precision)
FOLD_DIFF = 3

# absolute score lower threshold (accuracy)
MIN_SCORE = 0.8

# dictionaries to map raw (Mongo) data fields to those expected by SQL database:

# id integer primary key autoincrement,
# source text not null,
# uname text,
# uuid text not null,
# record_id text not null,
# document text not null,
# link text not null,
# date text not null,
# nlp_score real not null,
# nlp_cat text,
# nlp_warn text

DATA_DICTS = {"twitter": {"record_id": "id", # uname fetch is hardcoded below :(
                         "document": "text"}, # as are date and link generation :( :(
                 
                 "rss": {"uname": "user_name",
                         "record_id": "checksum",
                         "document": "description",
                         "link": "parsed_link",
                         "_date": "pub_date"} }

# NLP tagging will add each of the following to a record:
# "nlp_score"
# "nlp_cat"
# "nlp_warn"

# default training data is for twitter data
train_file = config["nlp"]["default_dir"] + config["nlp"]["twitter"]["train"]
co_value = config["nlp"]["twitter"]["co_value"]

##
## FUNCTIONS
##

def tweet_url_builder(uname, status_id, url_1="https://twitter.com/", url_2="/status/"):
  try:
    assert type(uname) in [str, unicode] and int(status_id)
  except:
    print("Could not generate URL - check database for '#' entries", file=sys.stderr)
    return "#"
  url = url_1 + str(uname) + url_2 + str(status_id)
  return url

def backupSql(num_bak=5):
  '''backup sql database before modifying; default number of backups is 5'''
  db_file = config["sqlite3"]["db_file"]
  mod_time = os.path.getmtime(db_file)
  time_stamp = datetime.fromtimestamp(mod_time).strftime("%b-%d-%y-%H:%M:%S")
  bak = db_file + "_" + time_stamp
  # now copy live database - do we need to worry about corruption, if mid write?
  copyfile(db_file, bak)
  # now check number of backups, and preserve only those that are most recent
  all_bak = db_file + "_*"
  bak_files = glob.glob(all_bak)
  if len(bak_files) > num_bak:
    # we have too many backups, remove the old ones
    bak_dated = []
    for file in bak_files:
      mtime = os.path.getmtime(file)
      bak_dated.append( (mtime, file) )
    # sort by newest to oldest, and remove the oldest
    bak_dated = sorted(bak_dated, reverse=True)
    to_remove = bak_dated[num_bak:] #list of (date, file) tuples
    for file in to_remove:
      file_name = file[1]
      os.remove(file_name)

def batchCategorize(train_set, data_list, verbose=False):
  '''Input is a labeled training list and an unlabeled list of data'''
  scores_list = []
  model_train = ReducedRep(train_set)      
  model_train.format()
  model_train.getFeaturesRR()
  classifier = nltk.classify.NaiveBayesClassifier.train(model_train.trainRR)
  
  labels = sorted(classifier.labels())
  
  test = ReducedRep(data_list, is_labeled=False)

  # no need to format test
  # but, hacky way of getting the data into labled_train
  test.labeled_train = test.train_list
  test.getFeaturesRR(verbose=verbose)
  
  for i in range(len(test.trainRR)):
    # test.trainRR = list of feature dictionaries
    c = classifier.prob_classify(test.trainRR[i])
    # c.SUM_TO_ONE = False
    # getting a lot of false positives, i.e. "French == CVE" (basically)
    score, category, warn = validateClassification(c, labels)
    score_dict = {"nlp_score": score,
                  "nlp_cat": category,
                  "nlp_warn": warn}
    scores_list.append(score_dict)
  return scores_list

def validateClassification(classifier_obj, labels, fold_diff=FOLD_DIFF, min_score=MIN_SCORE):
  ''' scores a classification to determine if it is sufficiently accurate and precise'''
  # returns tuple of (score, category, warning); if category is None, then warning
  scores = []
  for l in labels:
    t = (classifier_obj.prob(l), l)
    scores.append(t)
  ranked_scores = sorted(scores, reverse=True)
  if ranked_scores[0][0] >= min_score:
  # top score has achieved the minimum accuracy / confidence score, but what is the distribution?
    if (ranked_scores[1][0]/ranked_scores[0][0]) < (1.0/fold_diff):
    # difference between top score and next highest is greater than FOLD_DIFF-X, e.g., greater than 5x
      return ranked_scores[0][0], ranked_scores[0][1], None
    else:
      return -2.0, None, "FailPrecisionCheck"
  else:
    return -1.0, None, "FailAccuracyCheck"

##
## CLASSES
##

class NlpTag(MongoIO, SQLio):
  def __init__(self, train_file=train_file, train_co=co_value, **kwargs):
    MongoIO.__init__(self, **kwargs)
    SQLio.__init__(self, **kwargs)
    self.train_file = train_file
    self.training_set = []
    self.train_co = train_co
    # self.model = None
    self._list_untagged = []
    self._tagging_queue = []
    self._nlp_scores = None
    self.nlp_tagged_records = []

  def fetch_untagged(self):
    '''pulls untagged content from MongoDB'''
    if self.collection is None:
      print("run set_collection(collection) to specify the target", file=sys.stdout)
    else:
      # remove anything in _list_untagged - this is a QC more than anything
      self._list_untagged = []
      database = self.m_db 
      target_db = self.client[database]
      target_collection = target_db[self.collection]
      for record in target_collection.find({"nlp_processed": {"$ne": True}}):
        data_dict = DATA_DICTS[self.collection]
        # formatted record, includes the data source when initialized
        fmt_record = {"_source": self.collection}
        for d in data_dict:
          fmt_record[d] = record[data_dict[d]] if data_dict[d] is not None else None
        # hardcoded exceptions for specific fields
        # rather than having to set conditions to pull sn out
        if self.collection == "twitter":
          fmt_record["uname"] = record["user"]["screen_name"]
          fmt_record["link"] = tweet_url_builder(record["user"]["screen_name"], record["id"])
          d = record["created_at"] # fmt: Thu Oct 01 21:34:10 +0000 2015
          d = d[4:20] + d[26:]
          dp = datetime.strptime(d, "%b %d %H:%M:%S %Y")
          fmt_record["_date"] = dp.isoformat()
        self._list_untagged.append(fmt_record)

  def clear_nlp_flag(self):
    '''Removes the NLP-processed flag from all records in the specified collection'''
    confirm = raw_input('''
Confirm that you wish to remove NLP tags from %s data
You must type "Yes" to continue:  ''' % self.collection)

    if confirm != "Yes":
      print("You did not confirm the remove tags operation, exiting...", file=sys.stderr)
      sys.exit(2)

    if self.collection is not None:
      database = self.m_db 
      target_db = self.client[database]
      target_collection = target_db[self.collection]
      result = target_collection.update_many({"nlp_processed": True}, {"$set": {"nlp_processed": False}})
      matched = result.matched_count
      modified = result.modified_count
      print("%s records were flagged; of those, %s were updated" % (str(matched), str(modified)), file=sys.stdout)
      count_flagged = target_collection.find({"nlp_processed": True}).count()
      print("Verification... %s records remain flagged" % count_flagged, file=sys.stdout)

  def batch_categorize(self):
    '''load training model and process all records that have been fetched (run fetch_untagged() method)'''
    if len(self._list_untagged) == 0:
      print("No untagged records have been collected; run fetch_untagged(), check logs, or run clear_nlp_flag()", file=sys.stderr)
    else:
      # process training set file to make sure it is of the correct format:
      # {score}\t{tag}\t{document} ==> {tag}\t{document}
      tr = FileIO(self.train_file)
      tr.read()
      tr_set = tr.data[:self.train_co]
      for line in tr_set:
        self.training_set.append(line.partition("\t")[2])

      # now that the training set is correctly formatted, we need to pull all of the content
      # from the _list_untagged into the _tagging_queue
      for item in self._list_untagged:
        self._tagging_queue.append(item["document"])

      # now run batchCategorize function to obtain scores:
      self._nlp_scores = batchCategorize(self.training_set, self._tagging_queue)

      # merge _list_untagged and _nlp_scores
      # first, verify that they are the same length
      try:
        assert len(self._list_untagged) == len(self._nlp_scores)
      except AssertionError:
        print("The number of untagged entries does not equal the number of returned scores. Check the logs?", file=sys.stderr)
        return

      for i in range(len(self._list_untagged)):
        d1 = self._list_untagged[i]
        d2 = self._nlp_scores[i]

        # merge dicts through shallow copy and update
        d3 = d1.copy()
        d3.update(d2)

        self.nlp_tagged_records.append(d3)

  def _update_datastore(self):
    '''After writing tagged records to SQL DB, this is called in write_nlp_records() to 
       update records in Mongo datastore with the {"nlp_processed": True} flag'''
    if self.collection == "twitter":
      database = self.m_db 
      target_db = self.client[database]
      target_collection = target_db[self.collection]

      for rec in self._list_untagged:
        _id = rec["record_id"]
        try:
          assert target_collection.find({"id": _id}).count() == 1
          target_collection.update({"id": _id}, { "$set": {"nlp_processed": True}})
        except e:
          print("Oops - something happened when trying to update MongoDB flags", file=sys.stderr)
          print(e, file=sys.stderr)
    # to-do: Add if for rss

  def write_nlp_records(self):
    '''Run after batch_categorize() to insert/replace categorized content records in SQL DB'''
    self.connect()

    for rec in self.nlp_tagged_records:
      keys = ",".join(rec.keys())
      qs = ",".join(list('?' * len(rec)))
      values = tuple(rec.values())
      self.conn.execute("insert or replace into cat_content (" + keys + ") values (" + qs + ");", values)

    self.conn.commit()
    self.conn.close()

    # after commiting new records, updated datastore with "has been processed" flags
    self._update_datastore()

##
## MAIN
##

def main(col, training_set=train_file):
  backupSql()

  tagging = NlpTag(train_file=training_set)
  tagging.set_collection(collection=col)
  tagging.fetch_untagged()
  tagging.batch_categorize()

  # states on categorization process
  total_tagged = len(tagging.nlp_tagged_records)
  tags_count = {}
  for rec in tagging.nlp_tagged_records:
    if rec["nlp_cat"] is not None:
      if rec["nlp_cat"] not in tags_count.keys():
        tags_count[rec["nlp_cat"]] = 1
      else:
        tags_count[rec["nlp_cat"]] += 1

  print("Total %s records processed: %s" % (col, str(total_tagged))) # , file=sys.stdout
  print("Total %s records tagged: %s" % ( col, str(sum( tags_count.values() )) ) ) # , file=sys.stdout
  for t in tags_count:
    print(" |-> %s: %s" % (t, str(tags_count[t])))

  tagging.write_nlp_records()

if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument("collection", choices=config["mongodb"]["collections"], help="specify target dataset",
                      required=True)
  parser.add_argument("-i", "--in", metavar="FILE", dest="in_file", default=None,
                    help="Optional training dataset. Default specified in config file", required=False)
  args = parser.parse_args()

  # we expect the training set of the format:
  # score \t label \t content
  # for each line

  if args.in_file:
    training_set = args.in_file
  else:
    training_set = train_file

  col = args.collection

  main(training_set, col)



