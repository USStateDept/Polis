#!/usr/bin/env python

### import ###

from __future__ import print_function
import sys
import json
import twitter
from datetime import datetime
from APIKeys import Keys
from time import sleep
import dataIO
from config import c as config
import batch_nlp as bn

### constants ###

AUTH = twitter.oauth.OAuth(Keys.OAUTH_TOKEN, Keys.OAUTH_TOKEN_SECRET, \
                           Keys.CONSUMER_KEY, Keys.CONSUMER_SECRET)

TWITTER_API = twitter.Twitter(auth=AUTH)

COOLDOWN = config["twitter"]["rate_limit"]

### functions ###

def getAuthors():
  sql = dataIO.SQLio()
  sql.connect()
  sql.cur.execute("SELECT twitter, pid as uid \
                   from person \
                   where twitter is not null \
                   UNION \
                   SELECT twitter, cid as uid \
                   from city \
                   where twitter is not null;")
  rows = sql.cur.fetchall()
  sql.conn.close()
  lst = []
  for row in rows:
    lst.append(row)
  # lst is array of tuples: ('username', 'uuid')
  return lst

### classes ###

class TimelineObj:

  def __init__(self, author, uuid):
    self.author = author
    self.uuid = uuid
    self.data = []

  def getTimeline(self, count=200):
    tl = TWITTER_API.statuses.user_timeline(screen_name=self.author, count=count)
    # store timeline as list, not custom iterator
    self.data = tl[:]
    for record in self.data:
      record['user']['uuid'] = self.uuid

### main ###

if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument("--nodb", help="runs without writing to database (stdout)", action="store_true")
  parser.add_argument("--debug", help="increased verbosity for debugging", action="store_true")
  args = parser.parse_args()

  if args.nodb is True:
    write_out = False
  else:
    write_out = True

  if args.debug is True:
    verbose = True
  
  author_list = getAuthors()

  for author in author_list:
    screen_name = author[0]
    uuid = author[1]
    timeline = TimelineObj(screen_name, uuid)
    timeline.getTimeline()
    if write_out is True:
      twitter_entry = dataIO.MongoIO()
      for record in timeline.data:
        # currently polls db for each tweet to see if it already exists
        # not sure this is the best approach...!
        is_new_entry = twitter_entry.matchExisting("twitter", "id", record["id"])
        if is_new_entry == True:
          twitter_entry.writeRecord("twitter", record)
    else:
      for record in timeline.data:
          print(json.dumps(record, sort_keys=True, indent=2))
    sleep(COOLDOWN)

  bn.main("twitter")
