# solguard — Solana token due-diligence agent
# One-command judge demo:  docker build -t solguard . && docker run --rm solguard check <MINT>
# No paid API keys, no local Python install needed.

FROM python:3.12-slim AS base
WORKDIR /app

# Build + install the package (src layout per pyproject.toml)
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir .

# Run as an unprivileged user (hygiene; the tool only makes public RPC reads)
RUN useradd -m solguard
USER solguard

ENTRYPOINT ["solguard"]
# Default command prints the check/explain help so `docker run --rm solguard`
# without args is still informative rather than an error.
CMD ["explain", "--help"]
