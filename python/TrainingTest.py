#!/usr/bin/env python

from __future__ import print_function
from reduced import *
import codecs
import re
import nltk
import sys
import random
from nltk.corpus import stopwords

training_data = "../Python/weighted_training_set_021616.tsv"
test_data = "../Documents/old/en-twitter.train"
# number of slices through the training data to see how appending lower-scoring
# training data affects the predictive capability
n_slices = 50

train = readFile(training_data)
TEST = readFile(test_data)

# since training data is already ranked, reading serially preserves this order
TRAIN = []                                                                      
for i in train:
  d = i.split("\t",1)[1]
  TRAIN.append(d)

train_length = len(TRAIN)

# fraction of train to add to each iteration
f_slice = train_length/float(n_slices)

# for i in range(sub_div):
#   train_div = {}
#   train_div["start"] = int(i*f_sub_div)
#   train_div["end"] = int((i+1)*f_sub_div)
#   train_div["content"] = train[train_div["start"]:train_div["end"]]
#   train_sets.append(train_div)

scores = []

for i in range(n_slices):
  # code borrowed from genetic training algorithm
  # iteratively expands the length of train_i by adding the increasingly
  # lower-scoring data points into the training set
  train_i = TRAIN[:int((i+1)*f_slice)]
  length = len(train_i)
  score = RRevalModel(train_i, TEST, verbose=False)
  print("Training with top %s data points... score = %s" % (length, score))
  scores.append(score)

print("")
for score in scores:
  print(score)