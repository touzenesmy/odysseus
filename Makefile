# Minimal convenience targets. `make help` lists them.
ANCHOR ?= specs/instance/voice-audit-anchor.md

.PHONY: help anchor-verify

help:  ## list available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /  /' | sort

anchor-verify:  ## verify the voice-audit anchor hash table against the working tree
	@python3 scripts/anchor_verify.py $(ANCHOR)
