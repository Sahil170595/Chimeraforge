# The default image follows the published package; CI explicitly selects candidate.
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016 AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 chimera

FROM base AS candidate
COPY requirements-candidate.txt /tmp/requirements-candidate.txt
COPY dist/*.whl /tmp/dist/
RUN pip install --require-hashes -r /tmp/requirements-candidate.txt \
    && pip install --no-deps /tmp/dist/*.whl \
    && rm -rf /tmp/dist /tmp/requirements-candidate.txt
USER chimera
WORKDIR /home/chimera
RUN python -c "from chimeraforge.mcp_server import build_server; build_server()"
ENTRYPOINT ["chimeraforge"]
CMD ["mcp"]

FROM base AS published
ARG CHIMERAFORGE_VERSION=""
RUN pip install "chimeraforge[mcp]${CHIMERAFORGE_VERSION:+==${CHIMERAFORGE_VERSION}}"
USER chimera
WORKDIR /home/chimera
RUN python -c "from chimeraforge.mcp_server import build_server; build_server()"
ENTRYPOINT ["chimeraforge"]
CMD ["mcp"]
