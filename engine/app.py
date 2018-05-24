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
import time
import threading

from .disambiguate import Disambiguator

log = logging.getLogger(__name__)

class DEngine(Flask):
	def __init__(self, work_queue, *args, **kwargs):
		super(DEngine, self).__init__(*args, **kwargs)
		#print("Hello DEngine World!")
		
		self._work_queue = work_queue
		
		log.info('Starting server...')
		
		self.route('/', methods=['GET'])(self.hello_world)
		self.route('/disambiguate', methods=['POST'])(self.disambiguate)
		
	def hello_world(self):
		return "Hello World!"
		
	def disambiguate(self):
		#print(request.headers)
		#print(request.is_json)
		#print(request.data)
		#print(request.get_json())
		
		data = request.get_json()
		
		self._work_queue.put(data['context'])
		#print(self._work_queue)
		#print(data.keys())
		
		return (data['context'], 200)