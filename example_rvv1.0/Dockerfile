ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3 python3-dev scons pkg-config \
    clang-18 lld-18 llvm-18 zlib1g-dev libprotobuf-dev protobuf-compiler \
    libboost-all-dev libhdf5-dev libpng-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
