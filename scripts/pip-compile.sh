#!/bin/bash

# exit when any command fails
set -e

# Add verbosity flag to see more details about dependency resolution
VERBOSITY="-v"  # Use -v for less detail, -vvv for even more detail

# First compile the common constraints of the full requirement suite
# to make sure that all versions are mutually consistent across files
uv pip compile \
    $VERBOSITY \
    --no-strip-extras \
    --output-file=requirements/common-constraints.txt \
    requirements/requirements.in \
    requirements/requirements-*.in \
    $1

# Compile the base requirements
uv pip compile \
    $VERBOSITY \
    --no-strip-extras \
    --constraint=requirements/common-constraints.txt \
    --output-file=requirements.txt \
    requirements/requirements.in \
    $1

# Compile additional requirements files
SUFFIXES=(dev help browser playwright voice lint litellm)

for SUFFIX in "${SUFFIXES[@]}"; do
    uv pip compile \
        $VERBOSITY \
        --no-strip-extras \
        --constraint=requirements/common-constraints.txt \
        --output-file=requirements/requirements-${SUFFIX}.txt \
        requirements/requirements-${SUFFIX}.in \
        $1
done

# Compile the aggregate "all" extra from the feature .in files.
# Kept out of SUFFIXES (and the common-constraints glob above) because it
# is a union of the others, not an independent source of requirements.
uv pip compile \
    $VERBOSITY \
    --no-strip-extras \
    --constraint=requirements/common-constraints.txt \
    --output-file=requirements/requirements-all.txt \
    requirements/requirements-lint.in \
    requirements/requirements-litellm.in \
    requirements/requirements-voice.in \
    requirements/requirements-help.in \
    requirements/requirements-browser.in \
    requirements/requirements-playwright.in \
    $1
