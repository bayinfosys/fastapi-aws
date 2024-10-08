build:
	python3 -m build --sdist

venv:
	virtualenv -p python3 venv
	source venv/bin/activate

test: venv
	python -m unittest tests
