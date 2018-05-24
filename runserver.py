#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import sys

from threading import Thread
from engine.app import DEngine
from engine.disambiguate import Disambiguator

log = logging.getLogger(__name__)

from queue import Queue


if __name__ == '__main__':
	work_queue = Queue()
	
	#Establish Logging
	logging.basicConfig(stream=sys.stdout, level=logging.INFO,
		format='%(asctime)s [%(module)11s] [%(levelname)7s] %(message)s')
	
	logging.getLogger("engine.app").setLevel(logging.INFO)
	logging.getLogger("engine.disambiguate").setLevel(logging.INFO)
	
	#Start-up DE Engine
	disam = Disambiguator(work_queue)
	disam.start()
	
	#Start-up Server
	app = DEngine(work_queue, __name__)
	app.run()