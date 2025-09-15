
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

# Set python version
ARG PYTHON_VERSION="3.12"

# Set FPROC HOME
ARG FPROC_HOME="/opt/files-processor"

# Set global CRON args
ARG CRON_TIME_STR="0 0 18 * *"

# Set Pycharm version
ARG PYCHARM_VERSION="2025.1"



######################################
## Stage 1: Install Python packages ##
######################################

# Create image
FROM python:${PYTHON_VERSION}-slim AS py_builder

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Set python environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install OS packages
RUN apt-get -y -qq update && \
    apt-get -y -qq upgrade && \
    apt-get -y -qq --no-install-recommends install \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /usr/src/app

# Upgrade pip and install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip wheel --no-cache-dir --no-deps \
    --wheel-dir /usr/src/app/wheels -r /tmp/requirements.txt



###############################################
## Stage 2: Copy Python installation folders ##
###############################################

# Create image
FROM python:${PYTHON_VERSION}-slim AS py_final

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Install OS packages
RUN apt-get -y -qq update && \
    apt-get -y -qq upgrade && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies from py_builder
COPY --from=py_builder /usr/src/app/wheels /wheels
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache /wheels/* && \
    rm -rf /wheels



#################################
## Stage 3: Create FPROC image ##
#################################

# Create FPROC image
FROM py_final AS fproc_builder

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Renew FPROC_HOME
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

# Set permissions of app files
RUN chmod -R ug+rw,o+r ${FPROC_HOME}



###########################################
## Stage 4: Install management packages  ##
###########################################

# Create image
FROM fproc_builder AS fproc_mgmt

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Install OS packages
RUN apt-get -y -qq update && \
    apt-get -y -qq upgrade && \
    apt-get -y -qq --no-install-recommends install \
        # install Tini (https://github.com/krallin/tini#using-tini)
        tini \
        # to see process with pid 1
        htop procps \
        # to allow edit files
        vim \
        # to run process with cron
        cron && \
    rm -rf /var/lib/apt/lists/*

# Setup cron to allow it run as a non root user
RUN chmod u+s $(which cron)

# Add Tini (https://github.com/krallin/tini#using-tini)
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]



######################################
## Stage 5: Setup FPROC core image  ##
######################################

# Create image
FROM fproc_mgmt AS fproc-core

# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive

# Renew FPROC_HOME
ARG FPROC_HOME

# Renew CRON ARGs
ARG CRON_TIME_STR

# Install OS packages
RUN apt-get -y -qq update && \
    apt-get -y -qq upgrade && \
    apt-get -y -qq --no-install-recommends install \
        # to check container health
        redis-tools \
        # to configure locale
        locales && \
    rm -rf /var/lib/apt/lists/*

# Configure Locale en_US.UTF-8
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# es_US.UTF-8 UTF-8/es_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales

# Set read-only environment variables
ENV FPROC_HOME=${FPROC_HOME}

# Set environment variables
ENV CRON_TIME_STR=${CRON_TIME_STR}

# Crear archivo de configuración de CRON
RUN printf "\n\
# Setup cron to run files processor \n\
${CRON_TIME_STR} /usr/local/bin/python ${FPROC_HOME}/main.py >> /proc/1/fd/1 2>> /proc/1/fd/1\n\
\n" > ${FPROC_HOME}/crontab.conf
RUN chmod a+rw ${FPROC_HOME}/crontab.conf

# Setup CRON for root user
RUN (cat ${FPROC_HOME}/crontab.conf) | crontab -

# Crear script de inicio.
RUN printf "#!/bin/bash \n\
set -e \n\
\n\
# Reemplazar tiempo ejecución automática del procesador de archivos \n\
crontab -l | sed \"/main.py/ s|^\S* \S* \S* \S* \S*|\$CRON_TIME_STR|g\" | crontab - \n\
\n\
# Ejecutar cron \n\
cron -fL 15 \n\
\n" > /startup.sh
RUN chmod a+x /startup.sh

# Crear script para verificar salud del contendor
RUN printf "#!/bin/bash\n\
if [ \$(find ${FPROC_HOME} -type f -name '*.pid' 2>/dev/null | wc -l) != 0 ] || \n\
   [ \$(echo 'KEYS *' | redis-cli -h \${REDIS_HOST} 2>/dev/null | grep -c files-processor) != 0 ] && \n\
   [ \$(ps -ef | grep -v 'grep' | grep -c 'python') == 0 ] \n\
then \n\
  exit 1 \n\
else \n\
  exit 0 \n\
fi \n\
\n" > /check-healthy.sh
RUN chmod a+x /check-healthy.sh

# Run your program under Tini (https://github.com/krallin/tini#using-tini)
CMD [ "bash", "-c", "/startup.sh" ]
# or docker run your-image /your/program ...

# Verificar si hubo alguna falla en la ejecución del replicador
HEALTHCHECK --interval=3s --timeout=3s --retries=3 CMD bash /check-healthy.sh



#####################################################
## Usage: Commands to Build and Run this container ##
#####################################################


# CONSTRUIR IMAGEN (CORE)
# docker build --force-rm \
#   --target fproc-core \
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
