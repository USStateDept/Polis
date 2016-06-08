#!/usr/bin/env python

### import ###

from __future__ import print_function
import sys
import xml.etree.cElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
import json
import urllib2
import socket
import ssl
import re
import hashlib
import dataIO
from config import c as config
from time import sleep


### testing ###


### constants ###

TEST_URL = "https://news.google.com/news?q=Boris%20Johnson&output=rss"
TEST_QUERY = "Boris Johnson"
GNEWS_URL = config["rss"]["gnews_url"]
C_LOWER = config["rss"]["lower_bound"]
COOLDOWN = config["rss"]["rate_limit"]

### functions ###

def buildQueries():
  sql = dataIO.SQLio()
  sql.connect()
  sql.cur.execute("SELECT fname, lname, title, pid \
                   from person;")
  rows = sql.cur.fetchall()
  sql.conn.close()
  lst = []
  for row in rows:
    query = '''"%s %s" %s''' % row[0:3]
    q_set = (query, row[3])
    lst.append(q_set)
  return lst

def formatURL(query, source=GNEWS_URL):
  if type(query) is not str:
    try:
      query = str(query)
      clean_input = True
    except:
      clean_input = False
  else:
    clean_input = True
  if clean_input is True:
    query = re.sub('\s', '+', query)
    target = source + query
    return target, clean_input
  else:
    return query, clean_input

### classes ###

class RSS:

  def __init__(self, url, pid):
    self.request = urllib2.urlopen(url, timeout=2.5)
    self.raw_rss_str = ""
    self.pid = pid
    self.root = None
    self.data = []

  def parseDescription(self, string):
    parsed_string = BeautifulSoup(string, 'html.parser')
    # try/except needed?
    return ' '.join([ s for s in parsed_string.stripped_strings ])

  def parseLink(self, link):
    #if '?' in l1...
    l1 = link.split('?')
    base_url = l1[0]
    l2 = l1[1].split('&')
    l_dict = {}
    for item in l2:
      params = item.split('=')
      key = params[0]
      value = params[1]
      l_dict[key] = value
    if l_dict['url']:
      return l_dict['url']
    else:
      return None

  def parseRssXml(self):
    if self.root is not None:
      for element in self.root.findall(".//item"):
        record = {}
        record['uuid'] = self.pid
        record['title'] = element.findall("./title")[0].text
        record['pub_date'] = element.findall("./pubDate")[0].text
        record['description'] = self.parseDescription(element.findall("./description")[0].text)
        record['link'] = element.findall("./link")[0].text
        record['parsed_link'] = self.parseLink(element.findall("./link")[0].text)
        # was checking 'parsed_link' hash, but there are several isses with using a derived field to generate unique id
        # must force .encode('utf-8') to avoid UnicodeEncodeError
        record['checksum'] = hashlib.md5(record['title'].encode('utf-8')).hexdigest()
        # No point in uuid if it's not going to be kept - need to validate as new record in DB first
        # self.data['uuid'] = str(uuid.uuid4())
        self.data.append(record)

  def getXmlRoot(self):
    data_str = self.request.read()
    try:
      self.root = ET.fromstring(data_str)
    except cElementTree.ParseError as e:
      self.root = None
      # better logging needed
      print(datetime.now().isoformat())
      print(url)
      print(date_str)
    if self.root is not None:
      self.raw_rss_str = ET.tostring(self.root)

  def getContent(self):
    for item in self.data:
      if verbose is True:
        print(item["parsed_link"])
      if item["parsed_link"] is not None:
        c_url = item["parsed_link"]
        try:
          c_request = urllib2.urlopen(c_url, timeout=5)
          c_str = c_request.read()
          c_parsed = BeautifulSoup(c_str, 'html.parser')
          # concatenates page title and all 'p' content that is greater than the defined cut-off into a single text field
          try:
            title = c_parsed.title.text
          except AttributeError, e:
            title = ''
            print("title error: %s" % e + item["parsed_link"], file=sys.stderr)
          
          text = []
          for p in c_parsed.find_all('p'):
            if p is not None and len(p.text) >= C_LOWER:
              text.append(p.text)
          
          # join title and text into a single field; if field length is < C_LOWER, remove the whole thing (to re-scan later?)
          item['content'] = ' '.join([title] + text)
          if len(item['content']) < C_LOWER:
            item['content'] = None
        except:
          e = sys.exc_info()[0]
          print("**WARNING: %s" % e)

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
  else:
    verbose = False

  query_list = buildQueries()
  for q_set in query_list:
    q = q_set[0]
    pid = q_set[1]
    url, is_clean = formatURL(q)
    if is_clean is False:
      err_str = "** WARNING: %s could not be used to generate a valid URL" % url
      print(err_str, file=sys.stderr)
    else:
      rss = RSS(url, pid)
      rss.getXmlRoot()
      rss.parseRssXml()
      rss.getContent()
      # now we have the complete record set, we need to check each and then write to the DB
      if write_out is True:
        rss_entry = dataIO.MongoIO()
        for record in rss.data:
          if rss_entry.matchExisting('rss', 'checksum', record['checksum']) is True:
            rss_entry.writeRecord('rss', record)
      else:
        for record in rss.data:
          print(json.dumps(record, sort_keys=True, indent=2))
    sleep(COOLDOWN)

