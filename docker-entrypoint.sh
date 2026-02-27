#!/bin/sh
set -e

# Fix ownership of the volume mount so appuser can write to it.
# Railway (and Docker in general) mounts volumes as root, overriding
# the chown done during image build. This must run as root before
# dropping privileges.
chown -R appuser:appuser /data

exec gosu appuser "$@"
