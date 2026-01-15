# Instructions on how to Run and/or Build your own Docker Container

## Build the Docker Container:

docker build . guard-demo --no-cache

## Run the Container:

docker run -it -p 3000:3000 guard-demo



## Use the pre-build DockerHub container. (Easiest - No need to pull the GIT repository locally and supports amd64 and arm64 processors)


docker run -it -p 3000:3000 vmummer/guard-demo

Current version in Docker Repository are amd64 and arm64 
