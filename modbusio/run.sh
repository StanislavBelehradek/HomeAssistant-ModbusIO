#!/usr/bin/with-contenv bashio
# Resolve MQTT connection details: prefer Supervisor-managed broker
# (declared via `services: ["mqtt:want"]`), fall back to manual add-on options.
set -e

if bashio::services.available "mqtt"; then
    bashio::log.info "Using Supervisor-managed MQTT broker"
    export MQTT_HOST
    export MQTT_PORT
    export MQTT_USERNAME
    export MQTT_PASSWORD
    MQTT_HOST=$(bashio::services "mqtt" "host")
    MQTT_PORT=$(bashio::services "mqtt" "port")
    MQTT_USERNAME=$(bashio::services "mqtt" "username")
    MQTT_PASSWORD=$(bashio::services "mqtt" "password")
else
    bashio::log.info "MQTT service not available, using manually configured broker"
    export MQTT_HOST
    export MQTT_PORT
    export MQTT_USERNAME
    export MQTT_PASSWORD
    MQTT_HOST=$(bashio::config "mqtt_host")
    MQTT_PORT=$(bashio::config "mqtt_port")
    MQTT_USERNAME=$(bashio::config "mqtt_username")
    MQTT_PASSWORD=$(bashio::config "mqtt_password")
fi

exec python3 -u -m app.main
