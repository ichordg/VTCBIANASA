# VTCBIANASA Project

_TODO: Get Baseline confidence_

A simple Python webserver to interface with a SenseGram-derived model for word-sense disambiguation. Created by VT CBIA 2017-2018 MSBA-BA students.

Installation
------------

This project is based on [SenseGram](https://github.com/tudarmstadt-lt/sensegram) and requires it to be installed. Current implementation requires it to be installed on the same level as this project. See the [makefile](https://github.com/ichordg/VTCBIANASA/blob/master/Makefile) for clarification.

The makefile in this project is still in a preliminary state and not guaranteed to fully deploy the project.

Usage
---

Run the server with
`python runserver.py`

Once running, the server listens on `http://localhost:5000/` for requests.

**Specific routes and methods:**
+ `../disambiguate` -- POST requests with JSON mimetype and data: `{"context":"This is an example context"}`
+ `../processExcel` -- POST requests with JSON mimetype and data: `{"path":"/path/to/excel/to/process.xlsx"}`
+ `../getSenses` -- POST requests with JSON mimetype and data: `{"word":"desiredWord"}`
