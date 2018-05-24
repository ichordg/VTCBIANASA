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
from threading import Thread
import time
from queue import Queue

log = logging.getLogger(__name__)

class Disambiguator(Thread):
	def __init__(self, work_queue):
		Thread.__init__(self)
		self.daemon = True
		self.name = 'disambiguator'
		
		self._work_queue = work_queue
		self._workers = []
		
		self.has_work = False
		
		#log.info('disambiguator hello world!')
		
		log.info('Initializing SenseGram')
		
		#TODO: Change from absolute to config/args
		sense_vectors_fpath = "../sensegram/model/nasa_001.clusters.minsize5-1000-sum-score-20.sense_vectors"
		word_vectors_fpath = "../sensegram/model/nasa_001.word_vectors"
		context_words_max = 3
		context_window_size = 5
		ignore_case = True
		lang = "en"
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
		while not self.has_work:
			if not self._work_queue.empty():
				print('Work Found!')
				self.has_work = True
		self.create_workers(1)
		
	
	def create_workers(self, num_workers):
		for i in range(num_workers):
			worker = DisambWorker(self._work_queue, self.wsd_model)
			worker.daemon = True
			worker.start()
			self._workers.append(worker)
	
class DisambWorker(Thread):
	
	def __init__(self, work_queue, wsd_model):
		Thread.__init__(self)
		self.log = logging.getLogger(__name__)
		self._running = True
		
		self._work_queue = work_queue
		self._model = wsd_model
		
		log.info('worker hello world!')
		
	def run(self):
		while self._running:
			context = self._work_queue.get()
			print(context)
			if not self._running:
				self._work_queue.put(context)
				self._work_queue.task_done()
				continue
			self._running = False
		print('Work finished!')
		
	def stop(self):
		self._running = False