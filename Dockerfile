
##################################################################
##                           README                             ##
##################################################################
## Este Dockerfile permite crear un contendor con todos los pa- ##
## quetes y todas las configuraciones necesarias para procesar  ##
## los pronósticos calibrados con PyCPT y EREG. El procesamien- ##
## implica tranformar archivos de salida al formato NetCDF.     ##
##################################################################



##########################
## Set GLOBAL arguments ##
##########################

# Set Python version
ARG PYTHON_VERSION="3.12"

# Set Python image variant
ARG IMG_VARIANT="-slim"

# Set FPROC HOME
ARG FPROC_HOME="/opt/files-processor"

# Set global CRON args
ARG CRON_TIME_STR="0 0 18 * *"



######################################
## Stage 1: Install Python packages ##
######################################

# Create image
FROM python:${PYTHON_VERSION}${IMG_VARIANT} AS py_builder

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Set python environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install OS packages
RUN apt-get --quiet --assume-yes update && \
    apt-get --quiet --assume-yes upgrade && \
    apt-get --quiet --assume-yes --no-install-recommends install \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /usr/src/app

# Upgrade pip and install dependencies
RUN python3 -m pip install --upgrade pip
# Copy dependencies from build context
COPY requirements.txt requirements.txt
# Install Python dependencies (ver: https://stackoverflow.com/a/17311033/5076110)
RUN python3 -m pip wheel --no-cache-dir --no-deps \
    --wheel-dir /usr/src/app/wheels -r requirements.txt



###############################################
## Stage 2: Copy Python installation folders ##
###############################################

# Create image
FROM python:${PYTHON_VERSION}${IMG_VARIANT} AS py_final

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Install OS packages
RUN apt-get --quiet --assume-yes update && \
    apt-get --quiet --assume-yes upgrade && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies from py_builder
COPY --from=py_builder /usr/src/app/wheels /wheels
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache /wheels/* && \
    rm -rf /wheels



##########################################
## Stage 3: Install management packages ##
##########################################

# Create image
FROM py_final AS base_image

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Install OS packages
RUN apt-get --quiet --assume-yes update && \
    apt-get --quiet --assume-yes --no-install-recommends install \
        # install Tini (https://github.com/krallin/tini#using-tini)
        tini \
        # to see process with pid 1
        htop procps \
        # to allow edit files
        vim \
        # to run process with cron
        cron && \
    rm -rf /var/lib/apt/lists/*

# Create utils directory
RUN mkdir -p /opt/utils

# Create script to load environment variables
RUN printf "#!/bin/bash \n\
export \$(cat /proc/1/environ | tr '\0' '\n' | xargs -0 -I {} echo \"{}\") \n\
\n" > /opt/utils/load-envvars

# Create startup/entrypoint script
RUN printf "#!/bin/bash \n\
set -e \n\
\043 https://docs.docker.com/reference/dockerfile/#entrypoint \n\
exec \"\$@\" \n\
\n" > /opt/utils/entrypoint

# Create script to check the container's health
RUN printf "#!/bin/bash \n\
exit 0 \n\
\n" > /opt/utils/check-healthy

# Set minimal permissions to the utils scripts
RUN chmod --recursive u=rx,g=rx,o=rx /opt/utils

# Allows utils scripts to run as a non-root user
RUN chmod u+s /opt/utils/load-envvars

# Setup cron to allow it to run as a non-root user
RUN chmod u+s $(which cron)

# Add Tini (https://github.com/krallin/tini#using-tini)
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]



#################################
## Stage 4: Create FPROC image ##
#################################

# Create FPROC image
FROM base_image AS fproc_builder

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Install OS packages
RUN apt-get --quiet --assume-yes update && \
    apt-get --quiet --assume-yes --no-install-recommends install \
        # to save scripts PID
        # to check container health
        redis-tools && \
    rm -rf /var/lib/apt/lists/*

# Renew ARGs
ARG FPROC_HOME

# Create FPROC_HOME folder
RUN mkdir -p ${FPROC_HOME}

# Copy project
COPY *.yaml ${FPROC_HOME}
COPY *.py ${FPROC_HOME}

# Create input and output folders (these folders are too big so they must be used them as volumes)
RUN mkdir -p ${FPROC_HOME}/descriptor_files
# Copy template.yaml (an example of a list of files to be processed)
COPY ./descriptor_files/template.yaml ${FPROC_HOME}/descriptor_files

# Save Git commit hash of this build into ${FPROC_HOME}/repo_version.
# https://github.com/docker/hub-feedback/issues/600#issuecomment-475941394
# https://docs.docker.com/build/building/context/#keep-git-directory
COPY ./.git /tmp/git
RUN export head=$(cat /tmp/git/HEAD | cut -d' ' -f2) && \
    if echo "${head}" | grep -q "refs/heads"; then \
    export hash=$(cat /tmp/git/${head}); else export hash=${head}; fi && \
    echo "${hash}" > ${FPROC_HOME}/repo_version && rm -rf /tmp/git

# Set minimum required permissions for files and folders
RUN find ${FPROC_HOME} -type f -exec chmod -R u=rw,g=rw,o=r -- {} + && \
    find ${FPROC_HOME} -type d -exec chmod -R u=rwx,g=rwx,o=rx -- {} +



#####################################
## Stage 5: Setup FPROC core image ##
#####################################

# Create image
FROM fproc_builder AS fproc_core

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Renew ARGs
ARG FPROC_HOME
ARG CRON_TIME_STR

# Install OS packages
RUN apt-get --quiet --assume-yes update && \
    apt-get --quiet --assume-yes --no-install-recommends install \
        # to configure locale
        locales && \
    rm -rf /var/lib/apt/lists/*

# Configure Locale en_US.UTF-8
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# es_US.UTF-8 UTF-8/es_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales

# Set locale
ENV LC_ALL en_US.UTF-8

# Create CRON configuration file
RUN printf "\n\
SHELL=/bin/bash \n\
BASH_ENV=/opt/utils/load-envvars \n\
\n\
\043 Setup cron to run files processor \n\
${CRON_TIME_STR} /usr/local/bin/python ${FPROC_HOME}/main.py >> /proc/1/fd/1 2>> /proc/1/fd/1\n\
\n" > ${FPROC_HOME}/crontab.conf

# Create startup/entrypoint script
RUN printf "#!/bin/bash \n\
set -e \n\
\n\
\043 Reemplazar tiempo ejecución automática del procesador de archivos \n\
sed -i \"/main.py/ s|^\d\S+\s\S+\s\S+\s\S+\s\S+\s|\$CRON_TIME_STR|g\" /opt/utils/crontab.conf \n\
crontab -l | sed \"/main.py/ s|^\d\S+\s\S+\s\S+\s\S+\s\S+\s|\$CRON_TIME_STR|g\" | crontab - \n\
\n\
exec \"\$@\" \n\
\n" > /opt/utils/entrypoint

# Create script to check the container's health
RUN printf "#!/bin/bash\n\
if [ \$(find ${FPROC_HOME} -type f -name '*.pid' 2>/dev/null | wc -l) != 0 ] || \n\
   [ \$(echo 'KEYS *' | redis-cli -h \${REDIS_HOST} 2>/dev/null | grep -c files-processor) != 0 ] && \n\
   [ \$(ps -ef | grep -v 'grep' | grep -c 'python') == 0 ] \n\
then \n\
  exit 1 \n\
else \n\
  exit 0 \n\
fi \n\
\n" > /opt/utils/check-healthy

# Set minimal permissions to the new scripts and files
RUN chmod u=rw,g=r,o=r ${EREG_HOME}/crontab.conf

# Set read-only environment variables
ENV FPROC_HOME=${FPROC_HOME}

# Set user-definable environment variables
ENV CRON_TIME_STR=${CRON_TIME_STR}

# Declare optional environment variables
ENV REDIS_HOST=localhost



######################################
## Stage 6: Setup FPROC final image ##
######################################

# Create image
FROM fproc_core AS fproc-root

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Renew ARGs
ARG FPROC_HOME

# Setup CRON for root user
RUN (cat ${FPROC_HOME}/crontab.conf) | crontab -

# Create standard directories used for specific types of user-specific data, as defined 
# by the XDG Base Directory Specification. For when "docker run --user uid:gid" is used.
# OBS: don't forget to add --env HOME=/home when running the container.
RUN mkdir -p /home/.local/share && \
    mkdir -p /home/.cache && \
    mkdir -p /home/.config
# Set permissions, for when "docker run --user uid:gid" is used
RUN chmod -R a+rwx /home/.local /home/.cache /home/.config

# Add Tini (https://github.com/krallin/tini#using-tini)
ENTRYPOINT [ "/usr/bin/tini", "-g", "--", "/opt/utils/entrypoint" ]

# Run your program under Tini (https://github.com/krallin/tini#using-tini)
CMD [ "cron", "-fL", "15" ]
# or docker run your-image /your/program ...

# Configurar verificación de la salud del contenedor
HEALTHCHECK --interval=3s --timeout=3s --retries=3 CMD bash /opt/utils/check-healthy

# Set work directory
WORKDIR ${FPROC_HOME}



#####################################################
## Usage: Commands to Build and Run this container ##
#####################################################


# CONSTRUIR IMAGEN (CORE)
# docker build --force-rm \
#   --target fproc-root \
#   --tag ghcr.io/danielbonhaure/files-processor:fproc-core-v1.0 \
#   --build-arg CRON_TIME_STR="0 0 18 * *" \
#   --file Dockerfile .

# LEVANTAR IMAGEN A GHCR
# docker push ghcr.io/danielbonhaure/files-processor:fproc-core-v1.0

# CORRER OPERACIONALMENTE CON CRON
# docker run --name files-processor \
#   --mount type=bind,src=/data/acc-cpt/output,dst=/opt/files-processor/descriptor_files/cpt-output \
#   --mount type=bind,src=/data/acc-cpt/input/predictands,dst=/opt/files-processor/descriptor_files/cpt-obs-data \
#   --mount type=bind,src=/data/acc-cpt/input/predictors,dst=/opt/files-processor/descriptor_files/cpt-predictors \
#   --mount type=bind,src=/data/ereg/generados/nmme_output,dst=/opt/files-processor/descriptor_files/ereg-output \
#   --detach ghcr.io/danielbonhaure/files-processor:fproc-core-v1.0

# CORRER MANUALMENTE
# docker run --name files-processor \
#   --mount type=bind,src=/data/acc-cpt/output,dst=/opt/files-processor/descriptor_files/cpt-output \
#   --mount type=bind,src=/data/acc-cpt/input/predictands,dst=/opt/files-processor/descriptor_files/cpt-obs-data \
#   --mount type=bind,src=/data/acc-cpt/input/predictors,dst=/opt/files-processor/descriptor_files/cpt-predictors \
#   --mount type=bind,src=/data/ereg/generados/nmme_output,dst=/opt/files-processor/descriptor_files/ereg-output \
#   --rm ghcr.io/danielbonhaure/files-processor:fproc-core-v1.0 \
# /usr/local/bin/python /opt/files-processor/main.py

# CORRER ARCHIVOS DE PRUEBA MANUALMENTE
# docker run --name files-processor \
#   --mount type=bind,src=$(pwd)/descriptor_files,dst=/opt/files-processor/descriptor_files \
#   --mount type=bind,src=$(pwd)/config.yaml,dst=/opt/files-processor/config.yaml \
#   --rm ghcr.io/danielbonhaure/files-processor:fproc-core-v1.0 \
# /usr/local/bin/python /opt/files-processor/main.py
