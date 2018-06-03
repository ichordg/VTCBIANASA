#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import sys
import configparser

from threading import Thread
from engine.app import DEngine
from engine.disambiguate import Disambiguator

log = logging.getLogger(__name__)

from queue import Queue


if __name__ == '__main__':
	work_queue = Queue()
	output_queue = {}
	
	#Establish Logging
	logging.basicConfig(stream=sys.stdout, level=logging.INFO,
		format='%(asctime)s [%(module)15s] [%(levelname)7s] %(message)s')
	
	logging.getLogger("engine.app").setLevel(logging.INFO)
	logging.getLogger("engine.disambiguate").setLevel(logging.INFO)
	
	#Scan Config file
	#TODO: Check to see if config file exists and use default values otherwise
	config = configparser.ConfigParser()
	config.read('config.ini')
	
	#Start-up DE Engine
	disam = Disambiguator(config, work_queue, output_queue)
	disam.start()
	
	#Start-up Server
	app = DEngine(config, work_queue, output_queue, __name__)
	app.run()