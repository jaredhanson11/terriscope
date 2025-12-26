#!/usr/bin/env sh

# This script is used to create a /config.js static file that can be used to dynamically load
# configuration values into the react frontend application. This is important because it
# allows environment variables used upon running the docker container to control values
# that are ultimately used in the static frontend code. This is notably different than
# passing environment variables to a node.js application, because the react frontend is
# built/static js code that is just served where node.js is a running process.

OUTPUT=/usr/share/nginx/html/config.js
echo "window.appConfig={}" >$OUTPUT
if [[ -n "$API_BASE_URL" ]]; then
    echo "window.appConfig.api_base_url=\"$API_BASE_URL\"" >>$OUTPUT
fi

REQUIRED_VARS=""
OPTIONAL_VARS=""
###### !! IMPORTANT !! ######
# Any value in OPTIONAL_VARS must have a default value defined in the defaultConfig of /src/app/config.ts

#### SET REQUIRED VARIABLES
# Set required variables and exit if some missing
MISSING_VARS=""

for VAR in $REQUIRED_VARS; do
    VALUE=$(eval echo \$$VAR)
    if [ -z "$VALUE" ]; then
        MISSING_VARS="$MISSING_VARS $VAR"
    else
        VAR_LOWER=$(echo "$VAR" | tr '[:upper:]' '[:lower:]')
        echo "window.appConfig.$VAR_LOWER=\"$VALUE\"" >>$OUTPUT
    fi
done

if [ -n "$MISSING_VARS" ]; then
    echo "Some required environment variables are not set."
    for VAR in $MISSING_VARS; do
        echo "$VAR is missing"
    done
    exit 1
fi

#### END REQUIRED VARIABLES

#### SET OPTIONAL VARIABLES

for OPTIONAL_VAR in $OPTIONAL_VARS; do
    OPTIONAL_VALUE=$(eval echo \$$OPTIONAL_VAR)
    if [ -z "$OPTIONAL_VALUE" ]; then
        continue
    else
        OPTIONAL_VAR_LOWER=$(echo "$OPTIONAL_VAR" | tr '[:upper:]' '[:lower:]')
        echo "window.appConfig.$OPTIONAL_VAR_LOWER=\"$OPTIONAL_VALUE\"" >>$OUTPUT
    fi
done

#### END OPTIONAL VARIABLES


echo "Final config.js file"
cat $OUTPUT
