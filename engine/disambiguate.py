#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging

#Importing Sensegram
import sys
sys.path.insert(0, '../sensegram')

import sensegram
from wsd import WSD
from gensim.models import KeyedVectors

#Other Imports
import spacy
import time
from queue import Queue
from threading import Thread

log = logging.getLogger(__name__)

class Disambiguator(Thread):
	def __init__(self, work_queue):
		Thread.__init__(self)
		self.daemon = True
		
		self._work_queue = work_queue
		self._workers = []
		
		self.has_work = False
		
		log.info('Loading spaCy model: \'en\'')
		start_time = time.time()
		self._spacy_model = spacy.load('en')
		seconds = time.time() - start_time
		log.info('Completed in {:5.2f} seconds'.format(seconds))
		
		#log.info('disambiguator hello world!')
		
		log.info('Initializing SenseGram')
		
		#TODO: Change from absolute to config/args
		sense_vectors_fpath = "../sensegram/model/nasa_001.clusters.minsize5-1000-sum-score-20.sense_vectors"
		word_vectors_fpath = "../sensegram/model/nasa_001.word_vectors"
		context_words_max = 3
		context_window_size = 5
		ignore_case = True
		lang = "en"
		#TODO: Change to false for deployment.
		verbose = True
		
		#Load model
		log.info('Loading sense vectors...')
		start_time = time.time()
		sv = sensegram.SenseGram.load_word2vec_format(sense_vectors_fpath, binary=False)
		seconds = time.time() - start_time
		log.info('Completed in {:5.2f} seconds'.format(seconds))
		
		log.info('Loading word vectors...')
		start_time = time.time()
		wv = KeyedVectors.load_word2vec_format(word_vectors_fpath, binary=False, unicode_errors="ignore")
		seconds = time.time() - start_time
		log.info('Completed in {:5.2f} seconds'.format(seconds))
		
		self.wsd_model = WSD(sv, wv, window=context_window_size, lang=lang,
				max_context_words=context_words_max, ignore_case=ignore_case, verbose=verbose)
		
		log.info('Model initialized successfully')
	
	#Disambiguation loop. Looks for entries on self._work_queue and initializes DisambWorkers when
	#work is found.
	def run(self):
		#TODO: Make continuous
		#while not self.has_work:
			#if not self._work_queue.empty():
				#print('Work Found!')
				#self.has_work = True
		#self.create_workers(1)
		
		while True:
			while not self._work_queue.empty():
				self.create_workers(1)
			
	
	def create_workers(self, num_workers):
		for i in range(num_workers):
			worker = DisambWorker(self._work_queue, self.wsd_model, self._spacy_model)
			worker.daemon = True
			worker.start()
			self._workers.append(worker)
	
class DisambWorker(Thread):
	def __init__(self, work_queue, wsd_model, spacy_model):
		Thread.__init__(self)
		self.log = logging.getLogger(__name__)
		self._running = True
		
		self._work_queue = work_queue
		self._model = wsd_model
		self._spacy_model = spacy_model
		
		log.info('Initializing worker...')
		
	def run(self):
		while self._running:
			context = self._work_queue.get()
			print(context)
			if not self._running:
				self._work_queue.put(context)
				self._work_queue.task_done()
				continue
			
			#Do the disambiguation
			log.info('Processing context: \"{}\"'.format(context))
			
			tokenized_context = self._spacy_model(context)
			
			result = []
			
			for token in tokenized_context:
				if not token.is_stop:
					result.append(self._model.disambiguate(context, token.text))
			
			print(result)
			
			#TODO: SQL integration
			
			#Fake SQL database
			test_dict = {
					"test#0" : 10001,
					"quick#0" : 10002,
					"brown#0" : 10003,
					"word#0" : 10004
				}
			#Final output array
			output = []
			
			#For every word in the disambiguation results array
			for word_pair in result:
				#if the sense ID is a key in the DB
				if word_pair[0] in test_dict:
					#Get the LaRC code, extend the ID to the tuple, add it to the ouptut
					word_pair = word_pair + (test_dict[word_pair[0]],)
					output.append(word_pair)
			
			print(output)
			
			#Extracting words without sense-tag
			for word_pair in result:
				word = word_pair[0][:word_pair[0].find('#')]
				print(word)
			
			self._running = False
		
		self._work_queue.task_done()
		log.info('Context: \"{}\" disambiguated successfully.'.format(context))
		
	def stop(self):
		self._running = False
		
	#Deprecated
	def find_target_word(self, context):
		tokens = self._spacy_model(context)
		tokens = [token.orth_ for token in tokens if not token.orth_.isspace()]
		print(tokens)
		return tokens[0]
		