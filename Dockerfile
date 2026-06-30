# syntax=docker/dockerfile:1

# Run from the fpga-sim directory:
    #### Build for x86 and ARM:
        # PRO TIP: run normal build command (last one listed) first
        # If both must be fully built, they run in parallel. On my Mac this took
        # over an hour, vs 18 minutes total when I built the native one, then
        # ran this (which reuses the cache and thus skips the native one)
    # docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/theharmonicrealm/fpga-sim-server:v2 .

    #### Export images in ARM and x86 format after building
    # docker image save --output fpga_sim_image_x86.tar ghcr.io/theharmonicrealm/fpga-sim-server:v2 --platform linux/amd64
    # docker image save --output fpga_sim_image_ARM.tar ghcr.io/theharmonicrealm/fpga-sim-server:v2 --platform linux/arm64
    
    #### Load the output of last command onto user machine
    # docker load -i fpga_sim_image_x86.tar
    # docker load -i fpga_sim_image_ARM.tar

    #### Normal build for current platform
    # docker buildx build -t ghcr.io/theharmonicrealm/fpga-sim-server:v2 .

    #### Push to GitHub:
    #### Log in (enter PAT on password prompt)
    # docker login ghcr.io -u TheHarmonicRealm
    #### Push
    # docker push ghcr.io/theharmonicrealm/fpga-sim-server:{current tag}

FROM ubuntu:22.04@sha256:fed6ddb82c61194e1814e93b59cfcb6759e5aa33c4e41bb3782313c2386ed6df
WORKDIR /usr/bin/


# apt-get must always be run this way in Dockerfiles

# Verilator core dependencies, plus git to download it
RUN apt-get update && apt-get install -y --no-install-recommends \
    git help2man perl python3 make autoconf g++ flex bison \
    mold ccache libgoogle-perftools-dev numactl perl-doc \
    git


# All of these are fine if they fail. Ignore with exit 0.
# Could omit, should fail for all Ubuntu images I think, but it feels more respectful of Verilator to not
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfl-dev; exit 0
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfl2; exit 0
RUN apt-get update && apt-get install -y --no-install-recommends \
    zlibc zlib1g zlib1g-dev; exit 0


# Download Verilator source to /usr/bin/
WORKDIR /usr/bin/
# fix git certificate issue
RUN apt-get update && apt-get install -y --no-install-recommends --reinstall \
    ca-certificates
RUN update-ca-certificates
RUN git clone https://github.com/verilator/verilator.git

# Build it
RUN unset VERILATOR_ROOT
WORKDIR verilator
RUN git pull
RUN git tag
# Freeze version. Relies on prints being a certain way, etc. Bad to update unpredictably if rebuild is needed.
RUN git checkout v5.046

RUN autoconf
RUN ./configure 
RUN make -j `nproc`
RUN make install


# Download uv then Python
RUN apt-get update && apt-get install -y --no-install-recommends curl
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

# Updating path wasn't working so just use absolute one for the one uv call
RUN uv python install 3.14



WORKDIR /root/fpga-sim
RUN mkdir user_inputs

COPY python/server__manager.py python/shared__util.py python/extract_ports.py .
COPY --exclude=Vtop.h server_materials .

EXPOSE 9834

# Dockerfile wizard set these
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Used by server manager to know if it is in Docker or not
ENV FPGA_DOCKER_SERVER="Yes this is the server"

CMD ["python3.14", "./server__manager.py"]