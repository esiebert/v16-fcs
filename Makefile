export PATH := ${HOME}/.local/bin:$(PATH)

install:
	poetry install

build:
	docker build -t fcs .

rm-container:
	@if [ "$$(docker ps -a -q -f name=fcs)" ]; then \
		docker rm fcs; \
	fi

run: build rm-container
	docker run --env-file .env --name fcs -p 8081:8081 --add-host=host.docker.internal:host-gateway fcs 
