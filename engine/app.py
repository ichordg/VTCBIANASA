#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import configparser
import uuid

#Importing Sensegram
import sys
sys.path.insert(0, '../sensegram')

import sensegram
from wsd import WSD
from gensim.models import KeyedVectors

#Other Imports
from flask import Flask, jsonify, render_template, request, abort, redirect, url_for, make_response, json
from flask.json import JSONEncoder
import time
import xlrd
import csv
import numpy as np
from threading import Thread

from .disambiguate import Disambiguator

log = logging.getLogger(__name__)

class DEngine(Flask):
	def __init__(self, config, work_queue, output_queue, *args, **kwargs):
		super(DEngine, self).__init__(*args, **kwargs)
		
		self._work_queue = work_queue
		self._output_queue = output_queue
		self._config = config
		
		log.info('Starting server...')
		
		self.route('/', methods=['GET'])(self.hello_world)
		self.route('/disambiguate', methods=['POST'])(self.disambiguate)
		self.route('/processExcel', methods=['POST'])(self.process_excel)
		self.route('/getSenses', methods=['POST'])(self.get_senses)
		
	def hello_world(self):
		return "Hello World!"
		
	def disambiguate(self):
		data = request.get_json()
		job_id = uuid.uuid4().hex
		
		self._work_queue.put((job_id, 'disambiguate', data['context']))
		
		while not job_id in self._output_queue:
			pass
		
		response = self._output_queue[job_id]
		
		return response
	
	def process_excel(self):
		data = request.get_json()
		path = data['path']
		
		parser = ExcelParser(path, self._work_queue, self._output_queue)
		parser.start()
		
		return('', 200)
	
	def get_senses(self):
		data = request.get_json()
		job_id = uuid.uuid4().hex
		
		print(data['word'])
		
		self._work_queue.put((job_id, 'get_senses', data['word']))
		
		while not job_id in self._output_queue:
			pass
		
		response = self._output_queue[job_id]
		
		return response
		
class ExcelParser(Thread):
	def __init__(self, path, work_queue, output_queue):
		Thread.__init__(self)
		self.daemon = True
		self._path = path
		self._work_queue = work_queue
		self._output_queue = output_queue
	
	def run(self):
		#evans code
		#file_location = () # location will vary
		#"/home/ichordg/DEVSPACE/handler/VTCBIANASAProject--OLD/GregPythonStuff/DraftBaselineScript.xlsx"
		workbook = xlrd.open_workbook(self._path)
		sheet = workbook.sheet_by_name('Sheet1')
		data = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]

		data = np.array(data)
		data = data[0:,:2]
		data = data[1:,:2].tolist()
		
		jobs = []
		
		for word, context in data:
			job_id = uuid.uuid4().hex
			
			job = (job_id, 'disambiguate', context)
			
			self._work_queue.put(job)
			jobs.append(job)
			
		
		output = []
		
		while True:
			if not jobs:
				print('Exiting Loop..')
				break
			for job in jobs:
				if job[0] in self._output_queue:
					jobs.remove(job)
					job += (self._output_queue[job[0]], )
					
					output.append(job)
					
			print(jobs)
		
		print(output)
		
		for row in data:
			for out in output:
				if out[2] in row:
					row.append(out[3].get_data())
		
		print(data)
		
		res = data
		csv_file = "/home/ichordg/deEngine/outputbook.csv"

		#Assuming res is a list of lists
		with open(csv_file, "w") as output:
			writer = csv.writer(output, lineterminator='\n')
			writer.writerows(res)