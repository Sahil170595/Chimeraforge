# Container image for the ChimeraForge MCP server.
#
# The server speaks MCP over stdio, so the container is run attached rather than
# as a daemon -- there is no port to publish and no healthcheck to poll:
#
#   docker run --rm -i chimeraforge
#
# Installed from the published wheel rather than the working tree so the image
# matches what a user actually gets from PyPI. Pass a version to pin it.
FROM python:3.12-slim AS base

# Build arg rather than a hardcoded pin: the default tracks the latest release,
# and CI/consumers can pin a known version for a reproducible image.
ARG CHIMERAFORGE_VERSION=""

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The planner itself is pure Python and needs no build toolchain; installing the
# wheel only keeps the image small and the attack surface boring.
RUN pip install --no-cache-dir "chimeraforge[mcp]${CHIMERAFORGE_VERSION:+==${CHIMERAFORGE_VERSION}}"

# Nothing here needs root, and an MCP server is something a user runs against
# their own machine -- so drop privileges rather than leaving it as an exercise.
RUN useradd --create-home --uid 10001 chimera
USER chimera
WORKDIR /home/chimera

# Fail the build if the server cannot actually be constructed, rather than
# shipping an image that only fails when someone tries to use it.
RUN python -c "from chimeraforge.mcp_server import build_server; build_server(); print('mcp server OK')"

ENTRYPOINT ["chimeraforge"]
CMD ["mcp"]
