clean:
	rm -drf dist

build: clean
	python3 -m build --sdist

venv:
	virtualenv -p python3 venv
	source venv/bin/activate

test: venv
	python -m unittest -v tests/*.py

coverage: venv
	coverage run -m unittest discover -s tests
	coverage report
