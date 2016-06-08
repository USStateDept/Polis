# Polis

Using open data to better understand subnational policy priorities

## Form and Function

Polis was created from a perceived need, as outlined in the 2015 [Quadrennial Diplomacy and Development Review](http://www.state.gov/s/dmr/qddr/) (QDDR), to better engage with subnational political actors (e.g., mayors and governors):

> Complementing traditional 
bilateral and multilateral negotiations already underway, we 
will engage subnational and citizen sectors on climate  issues, 
encouraging them to develop meaningful commitments and 
creative solutions to reduce greenhouse gas emissions. 

To obtain a comprehensive picture of subnational policy interests and priorities, Polis uses open data from and about these subnational actors in order understand how individual offices are dealing with the four strategic priorities of the Department:

+ Countering Violent Extremism (CVE)
+ Open Democratic Societies (ODS)
+ Inclusive Economic Growth (IEG)
+ Climate Change (CC)

Specifically: Polis ingests data from several sources, applies a Naive Bayesian content-categorization algorithm (a type of natural language processing, or NLP) to determine if the data pertain to the above poliy areas, and then serves an aggregate view (i.e., a profile) about each office included in the system. This allows for diplomats to better understand the needs, constrains, and interests of those with whom they interact, in order to more effectively promote US foreign policy and interests.

---

## Dependencies

### System
The app has been deployed in Ubuntu and Amazon Linux.
Flask's builtin debug server works well for testing, but we recommend using Apache webserver for production.

### Python
Created using version 2.7x. For older versions, _caveat emptor_. Not tested for python3 compatibly.

#### Packages:

BeautifulSoup 4 - https://www.crummy.com/software/BeautifulSoup/

crontab - https://pypi.python.org/pypi/python-crontab/

nltk - http://www.nltk.org/

pymongo - http://api.mongodb.com/python/current/

twitter - https://pypi.python.org/pypi/twitter

Flask - http://flask.pocoo.org/

**Recommended:** Use pip (sudo possibly required):
```
$ pip install beautifulsoup4
$ pip install python-crontab
$ pip install nltk
$ pip install pymongo
$ pip install twitter
$ pip install Flask
```

### MongoDB

https://www.mongodb.com/

Running on version 3.2.5. Newer versions are likely compatible; best to check pymongo documentation (above).

### Web (HTML/CSS/JS)

The webapp makes use of two frameworks:

Foundation for sites (v6.x) - http://foundation.zurb.com/sites.html

   CSS and JS components should be placed in the appropriate `python/webapp/static` subdirectories.

Chartist.js (responsive charts) - https://gionkunz.github.io/chartist-js/

   CSS and JS components should be placed in the `python/webapp/static/chartist-dist` directory.

---

## Getting started

This is a brief walkthrough for getting the system up and running.

1. Install and check all dependencies.
2. Initialize the SQLite3 database in the sql/ directory using schema.sql.

   Initial data load was done in-batch using the sqlite3 CLI, but the admin web interface could also be used.

4. Set up `config.py`:

   Copy `\_config.py` to `config.py`. `config.py` is not watched, as it contains secret information that should not be shared.
   `root_dir` should be set to the **full path** of the Polis root directory, and should NOT contain a trailing slash, e.g. `/home/ec2-user/polis`.
   `default_password` is for the Admin user of the web app, and should be reasonably strong, as this would allow others to edit data in your system.
   `secret_key` should be a random string of at least 32 characters; used to track sessions in the web app.

   Config has many other options that are set to defaults that will need to be changed based on your implementation. Data ingest is handeld by polis.py according to the schedules outlined in the "twitter" and "rss" blocks. The "nlp" section of config will need to be updated once a training dataset has been used to generate a model.

5. Set up `APIKeys.py`:

   Copy `\_APIKeys.py` to `APIKeys.py`. This is for the app-specific keys to the Twitter API.

6. Start MongoDB using the mongod daemon; Polis currently assumes the default port of 27017.

7. Running the content categorization tool on a training set:

   `$ python nbayes_classify.py {twitter|rss} --in {in_file} --test {test_file}`
   Both `in_file` and `test_file` should be in the "OpenNLP" style, tab-delimited and one "document" per line (curly braces should be omitted):

   {Label}{tab}{Content}

   The output of this is an ordered (most predictive to least) training set and a log file that will indicate the predictive capability of the training set as a function of set length. The config `co_value` should reflect the shortest training set length that generates effective predictions.

8. Start the data collection services using polis.py:

   `$ python polis.py start`

   You should be able to manually inspect the MongoDB document store after a cycle of collection has run. The polis subprocesses also write logs of the last cycle into the root Polis directory.

9. Start the webapp.

   `$ python polis_webapp.py`

   Please review Flask's documentation on setting the `DEBUG` flag in order to understand what it does, and the implications for your app.
