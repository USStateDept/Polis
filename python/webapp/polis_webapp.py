#!/usr/bin/env python

##
## IMPORTS
##

from __future__ import print_function
import sys
from datetime import datetime
import json
import re
import sqlite3
import uuid
import imp
from time import sleep
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

config = imp.load_source("config", "../config.py")
config = config.c

d = imp.load_source("dataIO", "../dataIO.py")

db_handler = d.SQLio()

##
## CONFIG
##

DEBUG = True
SECRET_KEY = config["webapp"]["secret_key"]
USERNAME = config["webapp"]["username"]
PASSWORD = config["webapp"]["default_pwd"]

##
## VARIABLES
##

# length of timeline in days
timeline_len = 30

##
## INIT FLASK
##

app = Flask(__name__)
app.config.from_object(__name__)

if DEBUG == True:
  print(app.config['USERNAME'])
  print(app.config['PASSWORD'])

##
## FUNCTIONS
##

def connect_db():
  '''Connects to the specific database.'''
  try:
    return sqlite3.connect(db_handler.db)
  except sqlite3.OperationalError:
    return sqlite3.connect("../../sql/polis.db")

def get_db():
    '''Opens a new database connection if there is none yet for the
    current application context.'''
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

##
## DECORATORS
##

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

##
## ROUTES
##

## VIEWER ROUTES

@app.route("/")
def home():
  '''Pulls current snapshot and summary stats for the main page'''
  # policy snapshot data
  
  '''
  labels: ['CVE', 'IEG', 'MACC', 'RODS'],
  series: [[8, 30, 16, 4]]
  '''

  cur = g.db.execute("""select nlp_cat, count(*)
                        from cat_content 
                        where nlp_cat is not null
                        and (julianday('now') - julianday(_date)) < 7
                        group by nlp_cat
                        order by nlp_cat asc;""")
  snap = cur.fetchall()
  
  # to mate data format...
  if snap != []:
    labels, series = zip(*snap)
    labels = [ str(label) for label in labels ]
    series = [list(series)]
  else:
    labels = []
    series = []
  
  #summary stats on number of figures, number labeled, and total captured content
  cur = g.db.execute("select count(*) from person;")
  p_count = cur.fetchall()[0][0]
  cur = g.db.execute("select count(*) from cat_content;")
  c_count = cur.fetchall()[0][0]
  cur = g.db.execute("select count(*) from cat_content where nlp_cat is not null;")
  l_count = cur.fetchall()[0][0]
  sum_stats = {"people_count": p_count, "content_count": c_count, "labeled_count": l_count}
  return render_template("home.html", sum_stats=sum_stats, labels=labels, series=series)



@app.route('/profiles')
def profiles():
  '''Renders the list of profiles'''
  cur = g.db.execute("""select p.title, c.city || "," as city, c.state || "," as state, c.country, p.fname, p.lname, p.id
                        from city c
                        join person_city_xref x on c.cid = x.cid
                        join person p on p.pid = x.pid
                        order by c.country, c.state, c.city;""")
  l = cur.fetchall()
  lst = [ {"title": i[0] + " of " + " ".join(i[1:4]), "name": " ".join(i[4:6]), "id": i[6]} for i in l]
  return render_template("profiles.html", lst=lst)



@app.route('/profiles/<uid>')
def show_profile_for(uid):
  '''Renders the city-specific profile page'''
  
  # return basic info: city, name, twitter handles
  cur = g.db.execute("""select p.title, c.city || "," as city, c.state || "," as state,
                      c.country, p.fname, p.lname, c.twitter as tw_c, p.twitter as tw_p
                      from city c
                      join person_city_xref x on c.cid = x.cid
                      join person p on p.pid = x.pid
                      where p.id = ?;""", (uid,))
  l = cur.fetchall()
  info = {"title": l[0][0] + " of " + " ".join(l[0][1:4]), "name": " ".join(l[0][4:6]), "tw_c": l[0][6], "tw_p": l[0][7]}
  
  # return policy profile
  cur = g.db.execute("""select nlp_cat, count(*)
                      from cat_content 
                      where uname in (
                          select p.twitter
                          from person_city_xref x
                          join person p on x.pid = p.pid
                          where p.id = ?
                          union
                          select c.twitter
                          from person_city_xref x
                          join person p on x.pid = p.pid
                          join city c on x.cid = c.cid
                          where p.id = ?)
                      and nlp_cat is not null
                      group by nlp_cat;""", (uid, uid))
  l = cur.fetchall()
  # to mate data format...
  try:
    labels, series = zip(*l)
    labels = [ str(label) for label in labels ]
    series = [list(series)]
  except ValueError:
    labels = ["NA"]
    series = [[0]]

  # return recent activity
  cur = g.db.execute("""select _source, uname, document, link, _date, nlp_cat
                      from cat_content
                      where nlp_cat is not null
                      and uname in (?,?)
                      order by _date DESC
                      limit 25;""", (info["tw_c"], info["tw_p"]))
  l = cur.fetchall()
  activity = []
  for i in l:
    d = {"source": i[0],
         "uname": i[1],
         "document": i[2],
         "link": i[3],
         "date": i[4],
         "category": i[5]
    }
    activity.append(d)

  return render_template("profile.html", info=info, labels=labels, series=series, activity=activity)



@app.route('/timeline')
def timeline():
  '''Pulls timeline data across all policy areas for the last six months'''
  
  '''
  Data format is -- 
  labels: ['Oct 2015', 'Nov 2015', 'Dec 2015', 'Jan 2016', 'Feb 2016'],
        series: [
          [120, 90, 70, 80, 50],
          [20, 10, 35, 70, 30],
          [10, 30, 40, 50, 60],
          [50, 10, 100, 30, 10]
        ]
  '''

  cur = g.db.execute("""select nlp_cat, date(_date) as date_, count(*)
                        from cat_content
                        where nlp_cat is not null
                        and date_ != date('now')
                        and (julianday('now') - julianday(date_)) <= ?
                        group by nlp_cat, date_;""", (timeline_len,))
  l = cur.fetchall()
  
  # create nested dict: d["label"]["date"] = count, for each label, date
  d = {}
  for i in l:
    if i[0] not in d.keys():
      d[i[0]] = {}
    d[i[0]][i[1]] = i[2]

  # create label list (dates)
  labels = []
  for key in d.keys():
    labels += d[key].keys()
  
  labels = [ str(label) for label in set(labels) ]
  labels.sort()

  # create list of lists, ordered by data_order list
  data_order = d.keys()
  data_order.sort()
  data = []
  for c in data_order:
    sub_data = []
    for t in labels:
      if t in d[c]:
        sub_data.append(d[c][t])
      else:
        sub_data.append(0)
    data.append(sub_data)

  # select 25 most recent items for feed at the bottom
  cur = g.db.execute("""select _source,uname,document, link, _date, nlp_cat
                        from cat_content
                        where nlp_cat is not null
                        order by _date DESC
                        limit 25;""")
  l = cur.fetchall()
  activity = []
  for i in l:
    d = {"source": i[0],
         "uname": i[1],
         "document": i[2],
         "link": i[3],
         "date": i[4],
         "category": i[5]
    }
    activity.append(d)

  return render_template("timeline.html", labels=labels, series=data, activity=activity)


@app.route("/about")
def about():
  return render_template("about.html")


## ADMIN ROUTES


@app.route('/update_list', methods=['GET'])
def update_list():
  '''Renders the list of profiles available to edit'''
  if not session.get('logged_in'):
      abort(401)
  cur = g.db.execute("""select p.title, c.city || "," as city, c.state || "," as state, c.country, p.fname, p.lname, p.id
                        from city c
                        join person_city_xref x on c.cid = x.cid
                        join person p on p.pid = x.pid
                        order by c.country, c.state, c.city;""")
  l = cur.fetchall()
  lst = [ {"title": i[0] + " of " + " ".join(i[1:4]), "name": " ".join(i[4:6]), "id": i[6]} for i in l]
  return render_template("update_list.html", lst=lst)


@app.route('/new', methods=['GET', 'POST'])
def add_entry():
  if not session.get('logged_in'):
      abort(401)

  if request.method == 'POST':
    cid = str(uuid.uuid4()) # create uuids for inserts
    pid = str(uuid.uuid4())
    name = request.form["p_fname"] + " " + request.form["p_lname"] 

    g.db.execute("""insert into city (cid, city, state, country, url, twitter)
                    values (?, ?, ?, ?, ?, ?)""", (cid, request.form["c_city"], request.form["c_state"],
                    request.form["c_country"], request.form["c_url"], request.form["c_twitter"]))
    g.db.execute("""insert into person (pid, fname, lname, name, title, twitter, url) 
                    values (?, ?, ?, ?, ?, ?, ?)""", (pid, request.form["p_fname"], request.form["p_lname"],
                    name, request.form["p_title"], request.form["p_twitter"], request.form["p_url"]))
    g.db.execute("""insert into person_city_xref (pid, cid, start_date) values (?, ?, date())""", (pid, cid))
    g.db.commit()

    flash('New entry was successfully posted')
    return redirect(url_for('update_list'))
  return render_template('add_entry.html')


@app.route('/update/<uid>', methods=['GET', 'POST'])
def update_entry(uid):
  if not session.get('logged_in'):
      abort(401)
  
  # if request.method == 'GET':
  cur = g.db.execute("""select c.city, c.state, c.country, p.title, p.fname, p.lname,
                        c.url, p.url, c.twitter, p.twitter 
                        from city c
                        join person_city_xref x on c.cid = x.cid
                        join person p on x.pid = p.pid
                        where p.id = ?;""", (uid,))
  l = cur.fetchall()
  profile = l[0] # ordered list, as per SQL query
  profile = [ "" if item is None else item for item in profile ]
  if DEBUG == True:
    print(profile)
  if request.method == 'POST': 
    # Do we need to make sure that we aren't inserting empty strings? Nope!
    # for item in request.form:
    #   if request.form[item] == "":
    #     request.form[item] = None

    g.db.execute("""update person
                   set title = ?,
                       fname = ?,
                       lname = ?,
                       url = ?,
                       twitter = ?
                   where id = ?;""", (request.form["p_title"], 
                                      request.form["p_fname"],
                                      request.form["p_lname"], 
                                      request.form["p_url"],
                                      request.form["p_twitter"], 
                                      uid)
                   )

    g.db.execute("""update city
                    set city = ?,
                        state = ?,
                        country = ?,
                        url = ?,
                        twitter = ?
                    where cid = (select cid 
                                 from person_city_xref 
                                 where pid = (select pid 
                                              from person 
                                              where id = ?
                                              )
                                );""", (request.form["c_city"],
                                        request.form["c_state"],
                                        request.form["c_country"],
                                        request.form["c_url"],
                                        request.form["c_twitter"],
                                        uid)
                    )
    g.db.commit()

    flash('Update successful')
    return redirect(url_for('update_list'))

  return render_template('update_entry.html', profile=profile)

@app.route('/login', methods=['GET', 'POST'])
def login():
  error = None
  if request.method == 'POST':
    if request.form['username'] != app.config['USERNAME'] or request.form['password'] != app.config['PASSWORD']:
        error_message = 'Invalid username or password'
        flash(error_message)
    else:
        session['logged_in'] = True
        flash('You were logged in')
        return redirect(url_for('home'))
  return render_template('admin.html')


@app.route('/logout')
def logout():
  session.pop('logged_in', None)
  flash('You were logged out')
  return redirect(url_for('home'))

##
## MAIN
##

if __name__ == '__main__':
  if DEBUG == False:
    app.run(host='0.0.0.0', port=80)
  else:
    app.run()