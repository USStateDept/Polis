#!/usr/bin/env python

##
## IMPORTS
##

from __future__ import print_function
#from reduced import *
from NBayes_Classify import *
import codecs
# import re
# import nltk
import sys
# import random
# from nltk.corpus import stopwords

##
## VARIABLES and CONSTANTS
##

training_file = "../Documents/optimized_training_011916_no-scores.tsv"
test_file = "../Documents/en-twitter-eval.txt"

## confidence metrics 

# fold above second highest score (precision)
FOLD_DIFF = 3

# absolute score lower threshold (accuracy)
MIN_SCORE = 0.6

##
## FUNCTIONS
##

def batchCategorize(train_set, test_set, verbose=False):
  model_train = ReducedRep(train_set)      
  model_train.format()
  model_train.getFeaturesRR()
  classifier = nltk.classify.NaiveBayesClassifier.train(model_train.trainRR)
  
  labels = sorted(classifier.labels())
  
  test = ReducedRep(test_set, is_labeled=False)

  # no need to format test
  # but, hacky way of getting the data into labled_train
  test.labeled_train = test.train_list
  test.getFeaturesRR(verbose=False)
  
  for i in range(len(test.trainRR)):
    # test.train_list == list of utf-8 strings
    # test.trainRR = list of feature dictionaries
    print(test.train_list[i].encode('utf-8'))
    c = classifier.prob_classify(test.trainRR[i])
    # c.SUM_TO_ONE = False
    # getting a lot of false positives, i.e. "French == CVE" (basically)
    for l in labels:
      print("%s: %s" % (l, c.prob(l)))
    print("")
    score, result = validateClassification(c, labels)
    if score < 0:
      print("N/A - not assigned a label (%s, %s)" % (score, result))
    else:
      print("** %s ** (%s)" % (result, score))
    print("-----------------------------")

def validateClassification(classifier_obj, labels, fold_diff=FOLD_DIFF, min_score=MIN_SCORE):
  ''' scores a classification to determine if it is sufficiently accurate and precise'''
  scores = []
  for l in labels:
    t = (classifier_obj.prob(l), l)
    scores.append(t)
  ranked_scores = sorted(scores, reverse=True)
  if ranked_scores[0][0] >= min_score:
  # top score has achieved the minimum accuracy / confidence score, but what is the distribution?
    if (ranked_scores[1][0]/ranked_scores[0][0]) < (1.0/fold_diff):
    # difference between top score and next highest is greater than FOLD_DIFF-X, e.g., greater than 5x
      return ranked_scores[0][0], ranked_scores[0][1]
    else:
      return -2, "FailPrecisionCheck"
  else:
    return -1, "FailAccuracyCheck"
    
##
## MAIN
##

if __name__ == '__main__':
  training_data = readFile(training_file)
  test_data = readFile(test_file)
  
  batchCategorize(training_data, test_data)