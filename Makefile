export LANG:=en_US.UTF-8
export SHELL:=/bin/bash


install:
	pip install -r requirements.txt
	cd ..
	git clone https://github.com/tudarmstadt-lt/sensegram.git
	cd sensegram
	make install