# Sidecar container for the Minecraft ECS task. Polls the Paper server's RCON console for
# player presence and publishes a binary CloudWatch metric (Minecraft/HostIsActive) used to
# drive the idle scale-down alarm. Runs alongside, not inside, the server container -- see
# activity_monitor.py for the polling/failure-handling logic itself.
FROM python:3.14-alpine

# Create a dedicated non-root user and group. Deliberately NOT uid/gid 1000: that uid is what
# the EFS access point's PosixUser is scoped to for the minecraft server container's data volume
# (see minecraft-core-stack.yaml). This container has no EFS mount and never should; using a
# different uid means it can't silently inherit write access to that volume if one were ever
# added to this container definition by mistake -- the mismatch would fail loudly instead.
RUN addgroup -g 2000 activity-monitor && \
    adduser -u 2000 -G activity-monitor -s /bin/sh -D activity-monitor

WORKDIR /app

# mcrcon and boto3 (and boto3's dependencies: botocore, urllib3, python-dateutil, jmespath) are
# all pure-Python packages -- no C extensions, so no build toolchain is needed on Alpine here.
RUN pip install --no-cache-dir mcrcon boto3

COPY activity_monitor.py /app/activity_monitor.py

RUN chown -R activity-monitor:activity-monitor /app

USER activity-monitor

CMD ["python3", "/app/activity_monitor.py"]
