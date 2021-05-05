#FROM debian:...
#FROM ubuntu:...

# needed to get 
RUN apt-get update

# prevent asking for timezone
#  ARG applies only during build
#  https://serverfault.com/a/1016972
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
RUN apt-get install -y tzdata

# many development tools
RUN apt-get install -y build-essential

# things omitted from build-essential
RUN apt-get install -y autoconf autoconf-archive automake libtool pkg-config
