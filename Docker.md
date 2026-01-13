# Instructions on how to Run and/or Build your own Docker Container

##To Build the Docker Container:

docker build . guard-demo --no-cache

##To Run the Container:

docker run -it -p 3000:3000 guard-demo



##If you wish to use the pre-build container:


docker run -it -p 3000:3000 vmummer/guard-demo

Current version in Docker Repository are amd64 and arm64 
