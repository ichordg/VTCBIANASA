#!/usr/bin/python
# -*- coding: utf-8 -*-

import configparser
import logging
import sys

#Importing Sensegram
sys.path.insert(0, '../sensegram')
import sensegram
from gensim.models import KeyedVectors
from wsd import WSD

#Other Imports
import pymysql.cursors
import spacy
import time
from flask import Flask, jsonify, render_template, request, abort, redirect, url_for, make_response, json
from flask.json import JSONEncoder
from queue import Queue
from threading import Thread

log = logging.getLogger(__name__)

# Main Disambiguation thread implementation
class Disambiguator(Thread):
	def __init__(self, config, work_queue, output_queue):
		# Initialize Disambiguator thread
		Thread.__init__(self)
		self.daemon = True
		
		# Setting up variables
		self._config = config
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._workers = []
		
		# Shouldn't have jobs yet
		self.has_work = False
		
		## Set up all the various models
		# spaCy
		log.warn('Loading spaCy model: \'en\'')
		start_time = time.time()
		self._spacy_model = spacy.load('en')
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
		# SenseGram
		log.info('Initializing SenseGram')
		
		# Figure out all the config file information
		sense_vectors_fpath = self._config['MODEL']['SENSE_VECTOR_PATH']
		word_vectors_fpath = self._config['MODEL']['WORD_VECTOR_PATH']
		context_words_max = int(self._config['MODEL']['CONTEXT_WORDS_MAX'])
		context_window_size = int(self._config['MODEL']['CONTEXT_WINDOW_SIZE'])
		ignore_case = self._config['MODEL'].getboolean('IGNORE_CASE')
		lang = self._config['MODEL']['LANG']
		
		# Really this should just be false unless you're debugging
		verbose = self._config['MODEL'].getboolean('VERBOSE')
		
		## Load model
		# Sense Vectors
		log.warn('Loading sense vectors...')
		start_time = time.time()
		sv = sensegram.SenseGram.load_word2vec_format(sense_vectors_fpath, binary=False)
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
		# Word Vectors
		log.warn('Loading word vectors...')
		start_time = time.time()
		wv = KeyedVectors.load_word2vec_format(word_vectors_fpath, binary=False, unicode_errors="ignore")
		seconds = time.time() - start_time
		log.warn('Completed in {:5.2f} seconds'.format(seconds))
		
		self._sense_vectors = sv
		self.wsd_model = WSD(sv, wv, window=context_window_size, lang=lang,
				max_context_words=context_words_max, ignore_case=ignore_case, verbose=verbose)
		
		log.info('Model initialized successfully')
	
	# Disambiguation loop. Looks for entries on self._work_queue and initializes DisambWorkers when
	# work is found.
	def run(self):		
		while True:
			while not self._work_queue.empty():
				# Flexibility to spin up more workers, or switch to a worker pool model, instead
				# of dynamic generation.
				self.create_workers(1)
			
	# Method to create workers-- passes the config, queues, models to the worker, then starts them.
	# Workers are appended to the 'worker' array. For now just used for debugging.
	def create_workers(self, num_workers):
		for i in range(num_workers):
			worker = DisambWorker(self._config, self._work_queue, 
				self._output_queue, self._sense_vectors, self.wsd_model, self._spacy_model)
			worker.daemon = True
			worker.start()
			self._workers.append(worker)
			

# Worker implementation
class DisambWorker(Thread):
	
	def __init__(self, config, work_queue, output_queue, sense_vectors, wsd_model, spacy_model):
		# Initialize the worker thread, set up logging, turn the worker on.
		Thread.__init__(self)
		self.log = logging.getLogger(__name__)
		self._running = True
		
		# Set up the worker's local variables.
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._config = config		
		self._sense_vectors = sense_vectors
		self._model = wsd_model
		self._spacy_model = spacy_model
		
		# Say hello, worker thread.
		log.info('Initializing worker...')
		
	def run(self):
		# Room to switch this worker from dynamic to pool model.
		while self._running:
			job_id, method, context = self._work_queue.get()
			if not self._running:
				self._work_queue.put((job_id, method, context))
				self._work_queue.task_done()
				continue
			
			## There's probably a much better way to do this...
			# uses eval to figure out which method to call, and calls that
			# method. Since every method returns a response object, shouldn't
			# cause problems.
			#TODO: Make this a safe eval!
			response = eval('self.{}(job_id, context)'.format(method))
			
			# We have a response, look up the job_id and put the response with
			# that ID, then turn off.
			self._output_queue[job_id] = response
			self._running = False
		
		self._work_queue.task_done()
		log.info('Job: {} completed.'.format(job_id))
	
	# If switched from dynamic, this method exists to turn the worker off.
	def stop(self):
		self._running = False
	
	# Implementation for addr/get_senses requests.
	def get_senses(self, job_id, word):
		log.info('Job: {}: Grabbing senses for: \"{}\"'.format(job_id, word))
	
		senses = self._sense_vectors.get_senses(word, ignore_case=True)
		
		sense_dict = {}
		
		# For each sense_id, prob pair in senses
		for sense_id, prob in senses:
			# Put (sense_id, (prob, {most_similar_words})) into the dict
			sense_dict[sense_id]={
				'probability':prob,
				'most_similar':{}
				}
			
			# Get the related senses
			rsense_dict={}
			# For each related sense, similarity score pair in the most similar senses
			# for the sense_id
			for rsense_id, sim in self._sense_vectors.wv.most_similar(sense_id):
				# Put (related sense, similarity score) into the dict.
				rsense_dict[rsense_id]=sim
			
			# Add the completed related senses dict back to the overall dict.
			sense_dict[sense_id]['most_similar']=rsense_dict
		
		
		# Flask has trouble using its dumps command and Python dicts, so make the response
		# manually. Fixable?
		response = Flask.response_class(
			response=json.dumps(sense_dict),
			status=200,
			mimetype='application/json'
		)
		
		return response
	
	# Disambiguation implementation
	def disambiguate(self, job_id, context):
		log.info('Job: {}: Processing context: \"{}\"'.format(job_id, context))
		
		# Let spaCy tokenize the context string
		tokenized_context = self._spacy_model(context)
		
		# result is an array containing all of the disambiguation results
		# indexed in decreasing confidence.
		result = []	

		# disam_dict is the dict used to store the disambiguations--
		# Stored as (token, disambiguation) key, value pairs.
		#TODO: Double-check spaCy tokenization-- is it unique?
		disam_dict = {}
		# Final output dict
		output = { 
			'context' : context,
			'disambiguation' : {}}
		
		# For each token in the tokenized context
		for token in tokenized_context:
			# if the token is not a stop word
			if not token.is_stop:
				# Fill in results, disambiguate, and add the result to disam_dict
				result.append(self._model.disambiguate(context, token.text))
				disam_dict[token.text] = self._model.disambiguate(context, token.text)
		
		#For every word in the disambiguation results array
		for word in disam_dict:
			# Grab the disambiguation results
			word_pair = disam_dict[word]
			
			# Connect to the MySQL DB via PyMySQL
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
					# Query the server for the id, description of the given senseID
					sql = "SELECT id, description FROM {} WHERE senseID=\'{}\'".format(
						self._config['MYSQL']['TABLE_NAME'], word_pair[0])
						
					cursor.execute(sql)
					
					#TODO: Something to confirm senseID is unique
					sql_result = cursor.fetchall()
					
					# if result is not empty
					if not all(sql_result):
						# Then we have a valid senseID-- add it to the word_pair tuple.
						word_pair += (sql_result[0],)
					else:
						# Otherwise put a blank for the larcID
						word_pair += ('',)
					# Finalizing the structure for disam_dict. Adding LaRC IDs.
					disam_dict[word] = {
						'sense':word_pair[0],
						'confidence':word_pair[1],
						'LaRC_ID':word_pair[2]}
			finally:
				connection.close()
		
		# append the completed disam_dict to the output dict.
		output['disambiguation'] = disam_dict
		
		# Build the JSON response-- Flask dumps has trouble with nested dicts, so
		# have to do it manually.
		response = Flask.response_class(
			response=json.dumps(output),
			status=200,
			mimetype='application/json'
		)
		
		return response