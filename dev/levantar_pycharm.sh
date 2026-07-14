#!/usr/bin/env bash


# Get the directory where the script is located
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Get the parent directory of the script's directory
PARENT_DIR="$(dirname "${SCRIPT_DIR}")"


# Print usage help message
usage() {
  echo -e "Usage: bash <script> [options] ... \n"
  echo -e "Script to build a PyCharm container image \n"
  echo -e "Options:"
  echo -e " -f, --force-build              \t Force container build."
  echo -e " -h, --help                     \t Display a help message and quit."
}

# Process script inputs
while [[ $# -gt 0 ]]; do
  case $1 in
    -f|--force-build) FORCE_BUILD=true; shift 1;;
    -h|--help|*) usage; exit;;
  esac
done


# Print script directory and parent directory
echo "Script directory: ${SCRIPT_DIR}"
echo "Parent directory: ${PARENT_DIR}"


# Definir algunos comandos útiles
readonly CONTAINER_PS='podman ps --format "{{.Names}}"'
readonly CONTAINER_IMAGES='podman images --filter "dangling=false" --format "{{.Repository}}:{{.Tag}}"'


# Crear imagen base (si no existe)
if [[ $(eval "${CONTAINER_IMAGES}" | grep -c pycharm-fproc) == 0 ]] || [[ "${FORCE_BUILD}" ]]; then
  # Crear imagen base
  podman build --format docker --pull \
    --target fproc-root \
    --tag ghcr.io/danielbonhaure/files-processor:fproc-core-vX.0 \
    --build-arg CRON_TIME_STR="0 0 18 * *" \
    --file "${PARENT_DIR}"/Dockerfile "${PARENT_DIR}"
  # Agregar PyCharm
  podman build --format docker --force-rm \
    --tag pycharm-fproc:latest \
    --build-arg BASE_IMAGE="ghcr.io/danielbonhaure/files-processor:fproc-core-vX.0" \
    --file "${PARENT_DIR}"/Dockerfile.pycharm "${PARENT_DIR}"
fi


# Levantar PyCharm
if [[ $(eval "${CONTAINER_PS}" | grep -c pycharm-fproc) == 0 ]]; then
  podman run --rm --detach \
    --name pycharm-fproc \
    --env GDK_BACKEND=wayland --env QT_QPA_PLATFORM=wayland \
    --env XDG_SESSION_TYPE=wayland \
    --env XDG_RUNTIME_DIR=/run/user \
    --env DBUS_SESSION_BUS_ADDRESS=/run/user/bus \
    --env WAYLAND_DISPLAY=wayland-0 \
    --mount type=bind,source=$XDG_RUNTIME_DIR/bus,target=/run/user/bus,readonly \
    --mount type=bind,source=$XDG_RUNTIME_DIR/at-spi/bus,target=/run/user/at-spi/bus,readonly \
    --mount type=bind,source=$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY,target=/run/user/wayland-0,readonly \
    --mount type=bind,source=/run/dbus/system_bus_socket,target=/run/dbus/system_bus_socket,readonly \
    --privileged \
    --mount type=bind,src="${PARENT_DIR}",dst=/opt/files-processor,relabel=shared \
    --workdir /opt/files-processor \
    --entrypoint "" \
    --tty --interactive pycharm-fproc:latest \
  pycharm -Dide.browser.jcef.enabled=false -Dawt.toolkit.name=WLToolkit -Dide.browser.jcef.log.level=verbose
fi



