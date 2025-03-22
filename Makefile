PROJECT_NAME=fastapi_aws
TAG?=$(shell git describe --tags)

.PHONY: build/image

clean:
	rm -drf dist
	docker rmi -f $(PROJECT_NAME):$(TAG)

test:
	python -m unittest -v tests/*.py

coverage:
	coverage run -m unittest discover -s tests
	coverage report

build/library: clean
	python3 -m build --wheel

build/image: build/library
	docker build -t $(PROJECT_NAME):$(TAG) -f Dockerfile .

test/image:
	docker run -it --rm $(PROJECT_NAME):$(TAG) --help
