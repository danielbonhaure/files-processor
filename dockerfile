
#############################
## Install python packages ##
#############################

# Create image
FROM python:3.9-slim-bullseye AS py_builder

# set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# set python environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install OS packages
RUN apt-get -y -qq update && \
    apt-get -y -qq --no-install-recommends install \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# set work directory
WORKDIR /usr/src/app

# upgrade pip and install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip wheel --no-cache-dir --no-deps \
    --wheel-dir /usr/src/app/wheels -r /tmp/requirements.txt



########################
## CREATE FINAL IMAGE ##
########################

# Create image
FROM python:3.9-slim-bullseye AS final_image

# set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Install OS packages
RUN apt-get -y -qq update &&\
    apt-get -y -qq --no-install-recommends install \
        # install Tini (https://github.com/krallin/tini#using-tini)
        tini \
        # to see process with pid 1
        htop \
        # to run sudo
        sudo \
        # to allow edit files
        vim \
        # to run process with cron
        cron && \
    rm -rf /var/lib/apt/lists/*

# Setup cron to allow it run as a non root user
RUN sudo chmod u+s $(which cron)

# Install python dependencies from py_builder
COPY --from=py_builder /usr/src/app/wheels /wheels
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache /wheels/* && \
    rm -rf /wheels

# Create work directory
RUN mkdir -p /opt/processor

# Set work directory
WORKDIR /opt/processor

# Copy app code
COPY . .

# Create input and output folders (these folders are too big so they must be used them as volumes)
RUN mkdir -p /opt/processor/descriptor_files



#######################
## SETUP FINAL IMAGE ##
#######################

# Create image
FROM final_image

# Set passwords
ARG ROOT_PWD="nonroot"
ARG NON_ROOT_PWD="nonroot"

# Pasar a root
USER root

# Modify root password
RUN echo "root:$ROOT_PWD" | chpasswd

# Create a non-root user, so the container can run as non-root
# OBS: the UID and GID must be the same as the user that own the
# input and the output volumes, so there isn't perms problems!!
ARG NON_ROOT_USR="nonroot"
ARG NON_ROOT_UID="1000"
ARG NON_ROOT_GID="1000"
RUN groupadd --gid $NON_ROOT_GID $NON_ROOT_USR
RUN useradd --uid $NON_ROOT_UID --gid $NON_ROOT_GID --comment "Non-root User Account" --create-home $NON_ROOT_USR

# Modify the password of non-root user
RUN echo "$NON_ROOT_USR:$NON_ROOT_PWD" | chpasswd

# Add non-root user to sudoers
RUN adduser $NON_ROOT_USR sudo

# Setup files processor
RUN chown -R $NON_ROOT_UID:$NON_ROOT_GID /opt/processor

# Setup cron for run once a month
RUN (echo "0 0 16 * * /usr/local/bin/python /opt/processor/main.py >> /proc/1/fd/1 2>> /proc/1/fd/1") | crontab -u $NON_ROOT_USR -

# Add Tini (https://github.com/krallin/tini#using-tini)
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]

# Run your program under Tini (https://github.com/krallin/tini#using-tini)
CMD ["cron", "-f"]
# or docker run your-image /your/program ...

# Access non-root user directory
WORKDIR /home/$NON_ROOT_USR

# Switch back to non-root user to avoid accidental container runs as root
USER $NON_ROOT_USR

# CONSTRUIR CONTENEDOR
# docker build -f dockerfile \
#        --build-arg ROOT_PWD=nonroot \
#        --build-arg NON_ROOT_PWD=nonroot \
#        --build-arg NON_ROOT_UID=$(stat -c "%u" .) \
#        --build-arg NON_ROOT_GID=$(stat -c "%g" .) \
#        -t file_processor .

# CORRER OPERACIONALMENTE CON CRON
# docker run --name file_processor --rm \
#        --volume $(pwd)/descriptor_files:/opt/processor/descriptor_files \
#        --volume $(pwd)/config.yaml:/opt/processor/config.yaml \
#        --detach file_processor:latest

# CORRER MANUALMENTE
# docker run --name file_processor --rm \
#        --volume $(pwd)/descriptor_files:/opt/processor/descriptor_files \
#        --volume $(pwd)/config.yaml:/opt/processor/config.yaml \
#        file_processor:latest /usr/local/bin/python /opt/processor/main.py
