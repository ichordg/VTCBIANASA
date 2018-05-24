# VTCBIANASA Project

#TODO:
Fix Elastic search to remove stop words
Fix JSON checks throughout to be based on numbers
Fix mimunimum confidence check and make sure if there is no LARC code or match we do something 

#EXTRA TODO:
Fix baseline confidence to be able to look at JSON object and not string






Full pipeline

STEP 1) INPUT
JSON Object {"context":"Hello World NASA!"}

STEP 2) FORMAT INPUT from JSON to String
Changes from json commandline argument with format {"context":"Hello World NASA!"} to "Hello World NASA!"

STEP 3) Identify target words using elasticsearch
Takes a stream of text and identifys the words we are going to disambiguate out of the inputSentence
Example input:	curl -X POST "localhost:9200/_analyze" -H 'Content-Type: application/json' -d' { "tokenizer": "classic", "text": " Hello World NASA." }'
Example output: example input: {"tokens":[{"token":"Hello","start_offset":1,"end_offset":6,"type":"<ALPHANUM>","position":0},{"token":"World","start_offset":7,"end_offset":12,"type":"<ALPHANUM>","position":1},{"token":"NASA","start_offset":13,"end_offset":17,"type":"<ALPHANUM>","position":2}]}
Need to make sure Elastic search is running See Appendix for running Elasticsearch

STEP 4) Clean the elasticsearch JSON Ouput
example input: {"tokens":[{"token":"Hello","start_offset":1,"end_offset":6,"type":"<ALPHANUM>","position":0},{"token":"World","start_offset":7,"end_offset":12,"type":"<ALPHANUM>","position":1},{"token":"NASA","start_offset":13,"end_offset":17,"type":"<ALPHANUM>","position":2}]}
example output: ['Hello', 'World', 'NASA']

STEP 5) Run Sensegram and find out sense and confidence
example input: runSensegram("NASA","Hello World NASA!")
example output: {'targetword': 'Greg', 'context': 'Hello World Greg!', 'sense': 'Greg#0', 'confidence': 1.0, 'LARCcode': 'LARCcode', 'worddefinition': 'worddefinition'}


STEP 6) Check the database to find LARC code and definition


OTHER FEATURES:

Extra Feature 1) Get Baseline confidence 
getbaselineConfidenceJSON(targetword, context):

Extra Feature 2) run excel parse
parses through excel document and pulls out acroynm and context
returns list of lists and excel workbook with two columns filled in

Extra Feature 3) appends LARC code to word 



Currently Working:
Steps 1, 2, 5.

Installation:
Directory structure
~/Sensegram
~/VTCBIANASA

Make sure Sensegram is installed and working on the same level as the project folder

1) Install Sensegram
2) Install this repo
3) cd into this repo
4) python runserver.py will initialize the server.
5) send POST requests to localhost:5000/disambiguate, with header application/json and data {context:some string}
