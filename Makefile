# solguard — quick targets for dev + judging.
# PITFALL: Make uses tabs, not spaces (this file uses tabs; do not re-indent).

.PHONY: test docker-build demo demo-bonk demo-batch help

test:          ## run the unit suite (no network)
	python3 -m pytest tests/ -q

docker-build:  ## build the solguard image
	docker build -t solguard .

# --- one-command judge demos (no Python/deps required on the host) ---

demo-bonk: docker-build          ## live explain on BONK mainnet (authorities revoked, clean)
	docker run --rm solguard explain DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263

demo-usdc: docker-build          ## live explain on USDC mainnet (mint+freeze live -> CAUTION)
	docker run --rm solguard explain EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

demo-batch: docker-build         ## live portfolio scan across two mints, riskiest-first
	docker run --rm solguard batch EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263

help:                            ## show all targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'
