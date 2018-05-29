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
from flask import Flask, jsonify, render_template, request, abort, redirect, url_for, make_response, json
from flask.json import JSONEncoder
import spacy
import pymysql.cursors
import time
from queue import Queue
from threading import Thread

log = logging.getLogger(__name__)

class DBCache:
	#Fields for DB managment
	#TODO: Move to a config file
	TIME_OF_LAST_REFRESH = 0.0
	MIN_TIME_TO_REFRESH = 86400
	
	DB_CACHE = {}
	

class Disambiguator(Thread):
	def __init__(self, work_queue, output_queue):
		Thread.__init__(self)
		self.daemon = True
		
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._workers = []
		
		self.refreshDB()
		
		DBCache.TIME_OF_LAST_REFRESH = time.time()
		
		self.has_work = False
		
		log.warn('Loading spaCy model: \'en\'')
		start_time = time.time()
		self._spacy_model = spacy.load('en')
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
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
		log.warn('Loading sense vectors...')
		start_time = time.time()
		sv = sensegram.SenseGram.load_word2vec_format(sense_vectors_fpath, binary=False)
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
		log.warn('Loading word vectors...')
		start_time = time.time()
		wv = KeyedVectors.load_word2vec_format(word_vectors_fpath, binary=False, unicode_errors="ignore")
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
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
			if (time.time() - DBCache.TIME_OF_LAST_REFRESH > DBCache.MIN_TIME_TO_REFRESH):
				self.refreshDB()
			
	
	def create_workers(self, num_workers):
		for i in range(num_workers):
			worker = DisambWorker(self._work_queue, self._output_queue, self.wsd_model, self._spacy_model)
			worker.daemon = True
			worker.start()
			self._workers.append(worker)
			
	def refreshDB(self):
		log.warn('Refreshing DB...')
		start_time = time.time()
		
		#TODO: Move vars to config
		connection = pymysql.connect(
			host='localhost',
			user='root',
			password='nasa2018',
			db='VTCBIADB',
			charset='utf8mb4',
			cursorclass=pymysql.cursors.DictCursor)
		try:
			with connection.cursor() as cursor:
				sql = "SELECT * FROM NASA2"
				cursor.execute(sql)
				result = cursor.fetchall()
				DBCache.DB_CACHE = result
				seconds = time.time() - start_time
				log.warn('Completed in {:5.2f} seconds'.format(seconds))
				#print(result)
		finally:
			connection.close()
		log.info('DB refreshed successfully')
		DBCache.TIME_OF_LAST_REFRESH = time.time()
	
class DisambWorker(Thread):
	def __init__(self, work_queue, output_queue, wsd_model, spacy_model):
		Thread.__init__(self)
		self.log = logging.getLogger(__name__)
		self._running = True
		
		self._work_queue = work_queue
		self._output_queue = output_queue
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
			#Final output array
			output = []
			
			#For every word in the disambiguation results array
			for word_pair in result:
				connection = pymysql.connect(
					host='localhost',
					user='root',
					password='nasa2018',
					db='VTCBIADB',
					charset='utf8mb4',
					cursorclass=pymysql.cursors.DictCursor)
				try:
					with connection.cursor() as cursor:
						sql = "SELECT id, description FROM NASA2 WHERE senseID=\'{}\'".format(word_pair[0])
						cursor.execute(sql)
						result = cursor.fetchall()
						print(result)
						if not all(result):
							word_pair += (result[0],)
						else:
							word_pair += ('',)
						print(word_pair)
						output.append(word_pair)
				finally:
					connection.close()
			
			print(output)
			
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
		