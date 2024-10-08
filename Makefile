build:
	@echo lol

venv:
	virtualenv -p python3 venv
	source venv/bin/activate

test: venv
	python -m unittest tests
