#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import configparser

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

class Disambiguator(Thread):
	def __init__(self, config, work_queue, output_queue):
		Thread.__init__(self)
		self.daemon = True
		
		self._config = config
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._workers = []
		
		self.has_work = False
		
		log.warn('Loading spaCy model: \'en\'')
		start_time = time.time()
		self._spacy_model = spacy.load('en')
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
		#log.info('disambiguator hello world!')
		
		log.info('Initializing SenseGram')
		
		#TODO: Change from absolute to config/args
		sense_vectors_fpath = self._config['MODEL']['SENSE_VECTOR_PATH']
		word_vectors_fpath = self._config['MODEL']['WORD_VECTOR_PATH']
		context_words_max = int(self._config['MODEL']['CONTEXT_WORDS_MAX'])
		context_window_size = int(self._config['MODEL']['CONTEXT_WINDOW_SIZE'])
		ignore_case = self._config['MODEL'].getboolean('IGNORE_CASE')
		lang = self._config['MODEL']['LANG']
		#TODO: Change to false for deployment.
		verbose = self._config['MODEL'].getboolean('VERBOSE')
		
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
		
		self._sense_vectors = sv
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
			worker = DisambWorker(self._config, self._work_queue, 
				self._output_queue, self._sense_vectors, self.wsd_model, self._spacy_model)
			worker.daemon = True
			worker.start()
			self._workers.append(worker)
			
	
class DisambWorker(Thread):
	
	def __init__(self, config, work_queue, output_queue, sense_vectors, wsd_model, spacy_model):
		Thread.__init__(self)
		self.log = logging.getLogger(__name__)
		self._running = True
		
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._config = config
		
		self._sense_vectors = sense_vectors
		self._model = wsd_model
		self._spacy_model = spacy_model
		
		log.info('Initializing worker...')
		
	def run(self):
		while self._running:
			job_id, method, context = self._work_queue.get()
			print(job_id)
			print(method)
			if not self._running:
				self._work_queue.put((job_id, method, context))
				self._work_queue.task_done()
				continue
			
			#There's probably a much better way to do this...
			response = eval('self.{}(context)'.format(method))
			
			self._output_queue[job_id] = response
			self._running = False
		
		self._work_queue.task_done()
		log.info('Context: \"{}\" disambiguated successfully.'.format(context))
		
	def stop(self):
		self._running = False
		
	def get_senses(self, word):
		senses = self._sense_vectors.get_senses(word, ignore_case=True)
		
		sense_dict = {}
		
		for sense_id, prob in senses:
			sense_dict[sense_id]={
				'probability':prob,
				'most_similar':{}
				}
			rsense_dict={}
			for rsense_id, sim in self._sense_vectors.wv.most_similar(sense_id):
				rsense_dict[rsense_id]=sim
			sense_dict[sense_id]['most_similar']=rsense_dict
		
		print(sense_dict)
		
		response = Flask.response_class(
			response=json.dumps(sense_dict),
			status=200,
			mimetype='application/json'
		)
		
		return response
		
	def disambiguate(self, context):
		#Do the disambiguation
		log.info('Processing context: \"{}\"'.format(context))
		
		tokenized_context = self._spacy_model(context)
		
		result = []
		
		disam_dict = {}
		
		for token in tokenized_context:
			if not token.is_stop:
				result.append(self._model.disambiguate(context, token.text))
				disam_dict[token.text] = self._model.disambiguate(context, token.text)
		
		print(disam_dict)
		
		#TODO: SQL integration
		#Final output array
		output = { 
			'context' : context,
			'disambiguation' : {}}
		
		#For every word in the disambiguation results array
		for word in disam_dict:
			
			word_pair = disam_dict[word]
			#Connect to the MySQL DB via PyMySQL
			connection = pymysql.connect(
				host=self._config['MYSQL']['HOST'],
				port=int(self._config['MYSQL']['PORT']),
				user=self._config['MYSQL']['USER'],
				password=self._config['MYSQL']['PASSWORD'],
				db=self._config['MYSQL']['DB_NAME'],
				charset='utf8mb4',
				cursorclass=pymysql.cursors.DictCursor)
			try:
				with connection.cursor() as cursor:
					#Query the server for the id, description of the given senseID
					sql = "SELECT id, description FROM {} WHERE senseID=\'{}\'".format(
						self._config['MYSQL']['TABLE_NAME'], word_pair[0])
						
					print(sql)
					cursor.execute(sql)
					
					#TODO: Something to confirm senseID is unique
					result = cursor.fetchall()
					if not all(result):
						word_pair += (result[0],)
					else:
						word_pair += ('',)
					disam_dict[word] = {
						'sense':word_pair[0],
						'confidence':word_pair[1],
						'LaRC_ID':word_pair[2]}
			finally:
				connection.close()
		
		output['disambiguation'] = disam_dict
		
		response = Flask.response_class(
			response=json.dumps(output),
			status=200,
			mimetype='application/json'
		)
		
		return response