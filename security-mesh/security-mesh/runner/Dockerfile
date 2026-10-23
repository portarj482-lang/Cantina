# Build with a reviewed Foundry image pinned by digest:
# docker build --build-arg FOUNDRY_BASE_IMAGE=<image>@sha256:<digest> -t security-mesh-foundry:<version> runner
ARG FOUNDRY_BASE_IMAGE
FROM ${FOUNDRY_BASE_IMAGE}

USER 10001:10001
WORKDIR /work
ENTRYPOINT ["forge"]
