#!/usr/bin/env python

##
## IMPORTS
##

from __future__ import print_function
from copy import deepcopy
import argparse
import codecs
import re
import nltk
import sys
import glob
import operator
import random
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
from config import c as config
from dataIO import FileIO

##
## CONSTANTS and VARIABLES
##

## genetic algorithm modifiers

# number of selection events
num_se = config["nlp"]["go_vars"]["num_se"]

# training model evaluation upper bound
g_threshold = config["nlp"]["go_vars"]["score_threshold"]

# fraction of trainiing set to exclude as a test set
frac_test = config["nlp"]["go_vars"]["frac_test"]

# number of evalutation cycles
num_cycles = config["nlp"]["go_vars"]["num_cycles"]

# number by which to divide training set for each evalutation round 
sub_div = config["nlp"]["go_vars"]["sub_div"]
##

## evaluation parameters

# number of slices through the training data to see how appending lower-scoring
# training data affects the predictive capability
n_slices = 50

## text parsing rules / operands
sep = "\t"
hash_pat = re.compile("^#")
sn_pat = re.compile("^@")
split_on = '\s'
url_pat = re.compile("^http")
custom_stops = [u'.', u'@', u':', u';', u'rt', u"'s", u':', u'&', u'amp', u'!', u',', u'?', u'#', u'(', u')']

# confirm that nltk data have been aquired
nltk.download("stopwords")
nltk.download("punkt")

stops = set(stopwords.words('english') + custom_stops)



# boost the value of hashtags as a feature
# hash_boost = 1 

##
## FUNCTIONS
##
      
def splitToTrainTest(train_data, frac_test=frac_test, verbose=False):
  '''divides training set to make a randomly selected subset 
  for training (default - 95%) and testing (default - 5%)'''
  lst = train_data[:]
  random.shuffle(lst)
  length = len(lst)
  test_len = int(length*frac_test)
  if verbose:
    print("Total dataset length: " + str(length))
    print("Training set length: " + str(length-test_len) )
    print("Training set fraction: " + str(float(length-test_len)/length))
    print("")
  raw_test = lst[0:test_len]
  raw_train = lst[test_len:]
  return raw_train, raw_test

def cleanData(doc_list):
  # tokenize
  tokens = []
  for doc in doc_list:
    text_l = []
    ws_split = re.split(split_on, doc)
    for w in ws_split:
      # remove URLs and empty strings
      if not (url_pat.match(w) or w == u''):
        text_l.append(w)
  
    # rejoin text and 'properly' tokenize
    text = " ".join(text_l)
    text_l = nltk.word_tokenize(text)
    
    # stop words 
    text_l = [ w.lower() for w in text_l if w.lower() not in stops]
  
    # stemming
    p_stemmer = PorterStemmer()
    text_l = [p_stemmer.stem(t) for t in text_l]
    
    ## append cleaned text to list
    tokens.append(text_l)
  return tokens

def evalModel(train_set, test_set, verbose=False):
  ''' evaluates the accuracy of a reduced-represenation data set using a defined
  training set and test set '''
  model_train = ReducedRep(train_set)      
  model_test = ReducedRep(test_set)     
  model_train.format()
  model_test.format()    
  model_train.getFeaturesRR()
  model_test.getFeaturesRR()
  classifierRR = nltk.classify.NaiveBayesClassifier.train(model_train.trainRR)
  accuracy = nltk.classify.accuracy(classifierRR, model_test.trainRR)
  if verbose:
    print("** reduced accuracy **")
    print(str(accuracy))
    print("")
  return accuracy

def gOptimizeTraining(training_data,
                      g_threshold=g_threshold,
                      num_cycles=num_cycles,
                      sub_div=sub_div,
                      verbose=False,
                      write_out=False,
                      out_file=None):
  # g_threshold == satisfactory fitness level
  # num_cycles == iteration cap -- is this needed?
  # sub_div == number of individuals to break the initial training set into
  
  # iterable that counts up to num_cycles
  I = 0
  
  # inital train and test sets
  # test set is proportional to the initial training sets, after subdivision
  f = 1.0/sub_div
  train, TEST = splitToTrainTest(training_data, frac_test=f, verbose=False)
  # from here on out, TEST is locked, and all individuals draw from train 
  
  # This is the authoritative set to which we append selected subsets
  TRAIN = []
  TRAIN_META = [] # ? format
  
  # TRAIN_LOG is the per-round set that we append to TRAIN_META
  TRAIN_LOG = {'round': None, # int
               'scores': [], # list of float
               'top_score': None, # float
               'top_scorer': None # int - index of first top_score
               }
  
  TRAIN_META.append(deepcopy(TRAIN_LOG))
  
  '''
  Algorithm:
  1) Determine progress in training:
      - if g_threshold has been met, STOP 
      - if num_cycles has been reached, STOP 
      - if we consume all of train, STOP - this is the while loop
  2) For each round,
      - Split train (or remainder) into sub_div components
      - Append each component to top scorer from last round
      - Run test eval against TEST for each
      - Select top scorer - what about ties?
      - if the best score this round is less than that of previous, GO BACK
        (do we take the number 2 score as the seed, or just recombine and try
        again? GO BACK needs to be counted, and does it count against num_cycles?
        AS written currently, yes. GO BACK really just means "don't add to")
      - Extract this component from train and append to TRAIN
      - random shuffle remainder of train 
  '''
  while len(train)/sub_div > 0:
    if TRAIN_META[-1]['top_score'] >= g_threshold:
      break
    elif TRAIN_META[-1]['round'] >= num_cycles:
      break
    else:
      # total length of training remainder
      train_length = len(train)
      
      # fraction of train to allocate to each variant
      f_sub_div = train_length/float(sub_div)
      
      # initialize training set array:
      train_sets = []
      
      # if verbose:
      #   print("Length of train_sets: %s" % len(train_sets), file=sys.stdout)
      
      # Flag used to indicate that the round was not productive
      no_improvement = False
      
      # create annotated list of divisions so that we can test them and then 
      # refer back to them during evaluation of the test 
      for i in range(sub_div):
        train_div = {}
        train_div["start"] = int(i*f_sub_div)
        train_div["end"] = int((i+1)*f_sub_div)
        train_div["content"] = train[train_div["start"]:train_div["end"]]
        train_sets.append(train_div)
      
      # add the components of train to the TRAIN reference
      to_eval = []
      for i in range(len(train_sets)):
        to_eval.append(TRAIN + train_sets[i]["content"])
      
      # we now have the training sets for this round.
      # we need to evaluate each one, add the results to the log,
      # and then (1) determine which is best, and (2) if that is an improvement
      # if so, then add the winning subset to TRAIN and continue, else
      # repeat with TRAIN as-is
      log = deepcopy(TRAIN_LOG)
      log['round'] = I
      
      for tr_set in to_eval:
        score = evalModel(tr_set, TEST)
        log['scores'].append(score)
        
      log['top_score'] = max(log['scores'])
      
      # Here we are selecting the first set that reaches top_score
      # this is in the event that there is a tie
      top_scs = []
      for i in range(len(log['scores'])):
        if log['scores'][i] == log['top_score']:
          top_scs.append(i)
      
      # if verbose:
      #   print("Length of log['scores']: %s" % len(log['scores']), file=sys.stdout)
      #   print("Length of top_scs: %s" % len(top_scs), file=sys.stdout)
      #   print("top_scorer: %s" % top_scs[0], file=sys.stdout)
      
      log['top_scorer'] = top_scs[0]
      
      # All previous top scores
      top_scores = [TRAIN_META[i]['top_score'] for i in range(len(TRAIN_META))]
      
      # for the first round, we  update TRAIN and train
      # otherwise only update if the top_score has improved
      if (log['top_score'] > max(top_scores)) and (len(TRAIN_META) > 0):
      # if (log['top_score'] > TRAIN_META[-1]['top_score']) and (len(TRAIN_META) > 0):
        # We have improved TRAIN and need to update it with the additional content
        # as written, we only look to see if we did better than last round, 
        # not globally better, thus:
        # 0.55 --> 0.53 --> 0.54
        # is valid. What we want is "if top score is > all previous top scores..." 
        index = log['top_scorer']
        
        # if verbose:
        #   print("Index of top scorer: %s" % index, file=sys.stdout)
        
        TRAIN = TRAIN + train_sets[index]['content']
        # and remove this segment from train
        train = train[0:train_sets[index]['start']] + train[train_sets[index]['end']:]
      else:
        index = log['top_scorer']
        no_improvement = True
        # TRAIN and train are not modified
      
      # add to log, iterate I, and shuffle train
      TRAIN_META.append(log)
      
      if verbose:
        print("Round: %s" % I, file=sys.stdout)
        if no_improvement:
          print("** Round discarded - Max: %s **" % str(max(top_scores))[:5], file=sys.stdout)
        
        scores_str = log['scores'][:]
        # flag top scorer 
        scores_str[index] = "*" + str(scores_str[index])[:5]
        scores_str = "   ".join([str(i)[:5] for i in scores_str])
        print(scores_str, file=sys.stdout)
      
      I += 1
      random.shuffle(train)
  
  '''
  Training rounds are complete, now we need to:
  1) report if successful - final score, length, % of each tag
  2) (optionally) write out model so that it can be accessed easily
  3) 
  '''
  # report final score
  print("", file=sys.stderr)
  print("** Final score: %s (Max: %s)" % (max(top_scores), g_threshold), file=sys.stderr)
  print("** Length of training set: %s" % str(len(TRAIN)), file=sys.stderr)
  
  # determine composition of training set
  tags = [ t.split("\t")[0] for t in TRAIN ]
  tag_set = set(tags)
  tag_fracs = {tag: round(tags.count(tag)/float(len(TRAIN)), 3) for tag in tag_set}
  
  for tag in tag_fracs:
    print("** %s: %s" % (tag, tag_fracs[tag]), file=sys.stderr)
  
  print("", file=sys.stderr)
  
  if write_out == True:
    if out_file == None:
      for t in TRAIN[:10]:
        print(t.encode('utf-8'))
    elif out_file is not None:
      try:
        # writeFile(TRAIN, out_file)
        write_file = FileIO(out_file, TRAIN)
        write_file.write()
      except IOError:
        print("Could not open %s for writing" % out_file, file=sys.stderr)

  # return status is the top score - used in filenaming
  return round(max(top_scores), 3)

##
## CLASSES
##

class ReducedRep(object):
  def __init__(self, train_list, sep=sep, url_pat=url_pat, stops=stops, has_hashtags=True, is_labeled=True):
    self.train_list = train_list
    self.split_on = split_on
    self.sep = sep
    self.url_pat = url_pat
    self.stops = stops
    self.labeled_train = []
    self.trainRR = []
    self.train = []
    self.has_hashtags = has_hashtags
    self.is_labeled = is_labeled
    self.reduced_features = []
    
  def format(self):
    ''' reformats OpenNLP-style training data to NLTK-style'''
    for item in self.train_list:
      # partition does a single split of a string using 'sep'
      item_tup = item.partition(self.sep)
      labeled_text = (item_tup[0], item_tup[2])
      self.labeled_train.append(labeled_text)
  
  # def classify(self):
  #   try:
  #     nltk.cl
  
  def getFeaturesRR(self, verbose=False):
    ''' extract and format the feature set from the training data'''
    self.trainRR = []
    for item in self.labeled_train:
      # category label
      if self.is_labeled:
        label = item[0]
        document = item[1]
      else:
        document = item
        
      if verbose:
        print(document.encode('utf-8'))
      # working variables: string, list, dict, and set
      text = ""
      text_l = []
      text_d = {}
      text_s = set()
      '''
      Description of the algorith used to slice n' dice text into a 
      reduced representation of the input training data:
      
      1. input string is split on all whitespace
      2. URLs are removed - most do not have relevant content
      3. text is recobined into a single string and then 'properly' tokenized 
         using NLTK
      4. text is then lowercased and stopwords are removed
      5. a (deduplicated) set is created for the text
      6. the set is used to count frequencies in the cleaned text (#4)
      7. if the text is flagged to (possibly) contain #hashtags, then
          a. if a token in the set starts with '#', then
          b. '#' is trimmed from the front
          c. if the trimmed word is already in the text, then add this occurence
             and then multiply by the hash_boost
             Q: does order matter/complicate things here?
             Q: if someone were to use the same # multiple times, e.g. #yolo #yolo,
                would that cause problems?
          d. if it is NOT in the set, then just apply the multiplier (already couted)
      8. all tokens in the set are converted to a dictionary, {"token": count}
      9. all training data are rolled into a list of tuples, [(dict, label), ...]
      '''
      # split on whitespace...
      ws_split = re.split(self.split_on, document)         #1
      # in order to remove URLs
      for w in ws_split:
        # if string does not match URL AND is not empty
        if not (self.url_pat.match(w) or w == u''):       #2
          text_l.append(w)
      # rejoin partially cleaned string, properly tokenize, stopword removal, and lower
      text = " ".join(text_l)                             #3
      # word_tokenize appears to remove eol characters, which is good
      text_l = nltk.word_tokenize(text)
      text_l = [ w.lower() for w in text_l if w.lower() not in self.stops]  #4
      # nltk tokenizer appears to split on #tags ==> '#', 'tags'
      # below block reverses this split
      if self.has_hashtags == True and u'#' in text_l:
        l=[]
        iterable = iter(range(len(text_l)))
        for i in iterable:
          if text_l[i] == u'#' and i < len(text_l):
            s = ''.join([text_l[i], text_l[i+1]])
            l.append(s)
            iterable.next()
          else:
            l.append(text_l[i])
        text_l = l
      
      text_s = set(text_l)                                #5
      for w in text_s:
        key = w
        value = text_l.count(w)                           #6
        if self.has_hashtags == True:                     #7
          # if word is a hashtag (YOLO!), then trim it and apply the boost
          if w[0] == u'#':
            w = w[1:]
            # if we've already counted occurences of w, then we missed this one
            if w in text_d.keys():
              value += 1
              value *= hash_boost
            # otherwise, just apply the boost
            else:
              key = w # reassign
              value *= hash_boost
        text_d[key] = value                               #8
      if self.is_labeled:
        self.trainRR.append((text_d, label))                  #9
      else:
        self.trainRR.append(text_d)

  def getFeatures(self):
    ''' extract and format the feature set from the training data'''
    self.train = []
    for item in self.labeled_train:
      # category label
      label = item[0]
      # working variables: string, list, dict, and set
      text = ""
      text_l = []
      text_d = {}
      text_s = set()
      # split on whitespace...
      ws_split = re.split(self.split_on, item[1])         #1
      # in order to remove URLs
      for w in ws_split:
        # if string does not match URL AND is not empty
        if not (self.url_pat.match(w) or w == u''):       #2
          text_l.append(w)
      # rejoin partially cleaned string, properly tokenize, stopword removal, and lower
      text = " ".join(text_l)                             #3
      # word_tokenize appears to remove eol characters, which is good
      text_l = nltk.word_tokenize(text)
      text_s = set(text_l)                                #5
      for w in text_s:
        key = w
        value = text_l.count(w)                           #6
        if self.has_hashtags == True:                     #7
          # if word is a hashtag (YOLO!), then trim it and apply the boost
          if w[0] == u'#':
            w = w[1:]
            # if we've already counted occurences of w, then we missed this one
            if w in text_d.keys():
              value += 1
              value *= hash_boost
            # otherwise, just apply the boost
            else:
              key = w # reassign
              value *= hash_boost
        text_d[key] = value                               #8
      self.train.append((text_d, label))                  #9

  def rrToString(self):
    '''converts reduced represetation (self.train) to list of unicode strings'''
    rr = self.train
    # converts rr dictionary into list of terms, weighted by frequency 
    # and/or hash_boost (which must, therefor, be an int now!)
    # [ val for l in [ [k] * rr[100][0][k] for k in rr[100][0].keys() ] for val in l ]
    rr_features = []
    for i in range(len(rr)):
      label = rr[i][1]
      rr_dict = rr[i][0]
      # nested list comprehension that creates a flat list of features
      # resolves duplicate words and INTEGER hash_boost into multiple occurances of 
      # the same token
      rr_list = [ val for l in [ [k] * rr_dict[k] for k in rr_dict.keys() ] for val in l ]
      labeled_rr_str = label + sep + " ".join(rr_list)
      rr_features.append(labeled_rr_str)
    self.reduced_features = rr_features

##
## MAIN 
##

if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument("collection", choices=config["mongodb"]["collections"], help="specify target dataset")
  parser.add_argument("-i", "--in", metavar="FILE", dest="in_file", default=None,
                    help="Specify the input training FILE.", required=False)
  parser.add_argument("-s", "--sorted", metavar="FILE", dest="sorted_file", default=None,
                    help="Specify the input SORTED training FILE.", required=False)
  parser.add_argument("-t", "--test", metavar="FILE", dest="test_file", default=None,
                    help="Specify the input test FILE.", required=True)
  args = parser.parse_args()

  # file parameters
  in_file = args.in_file
  sorted_file = args.sorted_file

  if in_file == sorted_file == None:
    print("Must specify a file with either --in or --sorted", file=sys.stderr)
    sys.exit(2)

  out_path = config["nlp"]["default_dir"]
  out_temp_file = config["nlp"][args.collection]["temp_fl"]
  out_final_data = config["nlp"]["default_dir"] + config["nlp"][args.collection]["train"]
  in_test = args.test_file

  raw_test = FileIO(file_name=in_test)
  raw_test.read()
  test_data = raw_test.data

  if in_file is not None:

    raw_train = FileIO(file_name=in_file)
    raw_train.read()

    # list of tuples that hold filename and final scores
    files_scores = []
    
    for i in range(num_se):
      round_no = str(i)
      out = out_path + round_no + out_temp_file
      final_score = gOptimizeTraining(raw_train.data, sub_div=20, num_cycles=30, verbose=True, write_out=True, out_file=out)
      files_scores.append((out, final_score))
    
    # convert training sets into a single set, each weighted on 
    # 1) final score of the individual training sets 
    # 2) the frequency with which the indivudal item appears in different training sets 
    data_dict = {}
    
    ##
    ## could scoring/weighting be better indicated by multiplying by 1/score 
    ## rather than adding? does this seem reasonable?
    ##
    
    for t in files_scores:
      score = t[1]
      file = t[0]
      training_set = FileIO(file_name=file)
      training_set.read()
      for item in training_set.data:
        if item not in data_dict.keys():
          # if we've not yet encountered this entry, add the item and assign
          # the value of that round's final score 
          data_dict[item] = score 
        else:
          # if we've alrady seen this entry, add the value of the final score
          data_dict[item] += score
    
    # sort data by score, highest to lowest
    sorted_data = sorted(data_dict.items(), key=operator.itemgetter(1))
    sorted_data.reverse()
    
    # now we have the dictionary of the form
    # {"CVE\tsome tweet about CVE": 1.67, ...}
    
    # report on length, score distribution, etc.
    print("Combined training set length: %s" % str(len(sorted_data)), file=sys.stdout)
    # Max?
    # Min?
    # Mean?
    # std dev?
    
    write_data = []
    for item in sorted_data:
      string = unicode(item[1]) + u"\t" + item[0] 
      write_data.append(string)
      
    out_file = FileIO(data=write_data, file_name=out_final_data)
    out_file.write()

    # rather than re-read out_file, grab sorted data and do the evaluation on it directly:
    TRAIN = []
    train = sorted_data

    for item in train:
      d = item[0]
      TRAIN.append(d)

  if sorted_file is not None:
    raw_sorted = FileIO(file_name=sorted_file)
    raw_sorted.read()

    TRAIN = []
    for line in raw_sorted.data:
      l = line.partition(sep)[2]
      TRAIN.append(l)

  train_length = len(TRAIN)

  # fraction of train to add to each iteration
  f_slice = train_length/float(n_slices)

  print("Top n | score")
  for i in range(n_slices):
    # code borrowed from genetic training algorithm
    # iteratively expands the length of train_i by adding the increasingly
    # lower-scoring data points into the training set
    
    # input into evalModel should now be fixed
    train_i = TRAIN[:int((i+1)*f_slice)]
    length = len(train_i)
    
    score = evalModel(train_i, test_data, verbose=False)
    print(" %s | %s" % (length, score))


