#!/usr/bin/python
# -*- coding: utf-8 -*-

import configparser
import logging
import sys
import uuid

#Importing Sensegram
sys.path.insert(0, '../sensegram')
import sensegram
from gensim.models import KeyedVectors
from wsd import WSD

#Other Imports
import csv
import numpy as np
import time
import xlrd
from flask import Flask, jsonify, render_template, request, abort, redirect, url_for, make_response, json
from flask.json import JSONEncoder
from threading import Thread

log = logging.getLogger(__name__)

# Flask server implementation
class DEngine(Flask):
	def __init__(self, config, work_queue, output_queue, *args, **kwargs):
		# Initializing thread
		super(DEngine, self).__init__(*args, **kwargs)
		
		# Set-up local variables
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._config = config
		
		# Say hello
		log.info('Starting server...')
		
		# Establish routes and method calls.
		self.route('/', methods=['GET'])(self.hello_world)
		self.route('/disambiguate', methods=['POST'])(self.disambiguate)
		self.route('/processExcel', methods=['POST'])(self.process_excel)
		self.route('/getSenses', methods=['POST'])(self.get_senses)
	
	# For debug
	def hello_world(self):
		return "Hello World!"
	
	# disambiguate request implementation.
	def disambiguate(self):
		# extract JSON, generate a job ID
		data = request.get_json()
		job_id = uuid.uuid4().hex
		
		# Put the job into the queue.
		self._work_queue.put((job_id, 'disambiguate', data['context']))
		
		# Wait for the job to finish
		while not job_id in self._output_queue:
			pass
		
		# Grab the response
		response = self._output_queue[job_id]
		
		return response
	
	# processExcell request implementation.
	def process_excel(self):
		# extract JSON, generate a job ID
		data = request.get_json()
		path = data['path']
		
		# Instantiate an excelparser, start it.
		parser = ExcelParser(self._config, path, self._work_queue, self._output_queue)
		parser.start()
		
		return('', 200)
	
	# getSenses request implementation.
	def get_senses(self):
		# extract JSON, generate a job ID
		data = request.get_json()
		job_id = uuid.uuid4().hex
		
		# Put the job into the queue.
		self._work_queue.put((job_id, 'get_senses', data['word']))
		
		# Wait for the job to finish
		while not job_id in self._output_queue:
			pass
		
		# Grab the response
		response = self._output_queue[job_id]
		
		return response
	
# ExcelParser implementation	
class ExcelParser(Thread):
	def __init__(self, config, path, work_queue, output_queue):
		# Initialization
		Thread.__init__(self)
		self.daemon = True
		
		# Local variable set up.
		self._path = path
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._config = config
	
	def run(self):
		# Open the workbook at the passed path.
		workbook = xlrd.open_workbook(self._path)
		
		#TODO: Don't look for a specific sheet.
		sheet = workbook.sheet_by_name('Sheet1')
		data = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]

		data = np.array(data)
		data = data[0:,:2]
		data = data[1:,:2].tolist()
		
		# Array to hold all the jobs.
		jobs = []
		
		# For every word, context pair in the processed sheet data.
		for word, context in data:
			# Generate a job ID
			job_id = uuid.uuid4().hex
			
			# Make the job, put it into the queue and append it to our job array.
			job = (job_id, 'disambiguate', context)
			self._work_queue.put(job)
			jobs.append(job)
			
		# Array to hold the completed responses.
		output = []
		
		while True:
			# if we're out of jobs, exit the loop.
			if not jobs:
				break
			# For each job in the job array, if we find the job ID in the output queue
			# remove it from the jobs array. Add the output response to the job tuple,
			# then append the new tuple to the output array.
			for job in jobs:
				if job[0] in self._output_queue:
					jobs.remove(job)
					job += (self._output_queue[job[0]], )
					output.append(job)
		
		# For every processed row, for each output found, append the json in the 
		# response to the end of the row
		for row in data:
			for out in output:
				if out[2] in row:
					row.append(out[3].get_data())
		
		res = data
		csv_file = self._config['MISC']['OUT_PATH']

		# Assuming res is a list of lists. Generate the output file.
		with open(csv_file, "w") as output:
			writer = csv.writer(output, lineterminator='\n')
			writer.writerows(res)
			
		log.info('Processed Excel file written to {}'.format(self._config['MISC']['OUT_PATH']))