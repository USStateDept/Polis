#!/usr/bin/env python

### import ###

from __future__ import print_function
from crontab import CronTab
import sys
# import json
# from datetime import datetime
import argparse
# import os.path
import config

### constants ###

ROOT_DIR = config.DEFAULT["root_dir"]

SOURCES = []

TWITTER = {}
TWITTER["DAEMON"] = config.c["twitter"]["daemon"]
TWITTER["FREQ"] = config.c["twitter"]["frequency"]
TWITTER["LOGFILE"] = config.c["twitter"]["logfile"]
SOURCES.append(TWITTER)

RSS = {}
RSS["DAEMON"] = config.c["rss"]["daemon"]
RSS["FREQ"] = config.c["rss"]["frequency"]
RSS["LOGFILE"] = config.c["rss"]["logfile"]
SOURCES.append(RSS)

### functions ###

def servicesStart():
  cron = CronTab(user=True)
  for job in cron.find_comment('polis'):
    if job.comment == 'polis':
      print("**WARNING: Polis services already running -- run 'polis stop'", file=sys.stderr)
      sys.exit(2)
  for i in range(len(SOURCES)):
    root_dir = ROOT_DIR
    logfile = SOURCES[i]["LOGFILE"]
    daemon = SOURCES[i]["DAEMON"]
    freq = SOURCES[i]["FREQ"]
    command_string = "python " + root_dir + "/python/" + daemon + " > " + logfile + " 2>&1"
    job = cron.new(command=command_string, comment='polis')
    try:
      # first entry set to 0 -- otherwise a new script spawns every minute
      job.setall("0 %s * * *" % freq)
    except:
      print("**ERROR: Could not set %s" % daemon, file=sys.stderr)
      print("Check config.py for invalid frequency settings", file=sys.stderr)
      sys.exit(3)
  for job in cron:
    if job.is_valid():
      print(job.command)
    else:
      print("**ERROR: Invalid job: %s" % job.command)
      sys.exit(4)
  # assuming all goes well:
  cron.write()

def servicesStop():
  cron = CronTab(user=True)
  cron.remove_all(comment='polis')
  cron.write()

### classes ###

### main ###

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("services", choices=["start", "stop", "restart"], help="specify start, stop, or restart data collection services")
  args = parser.parse_args()

  if args.services == "start":
    servicesStart()
    sys.exit(0)
  elif args.services == "stop":
    servicesStop()
    sys.exit(0)
  elif args.services == "restart":
    servicesStop()
    servicesStart()
    sys.exit(0)

