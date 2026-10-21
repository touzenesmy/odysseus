# Outbound HTTPS trust

Odysseus uses both Python package CA bundles and system trust. HTTPX uses certifi by default; the guarded web/PDF fetcher and webhook delivery explicitly use Python's system SSL context. A configured `LLM_CA_BUNDLE` adds certificates to system trust for model calls. Upgrading certifi alone cannot repair every outbound HTTPS path.

For the October 2026 eMudhra incident, use certifi 2026.10.19 or newer, pip 26.2.2 or newer, and uv 0.13.4 or newer wherever uv is used. Pip has its own vendored certifi and also loads system roots. Update the operating system's certificate package separately. See the [Python security announcement](https://discuss.python.org/t/109576) and [incident details](https://emudhra.we-have-a-problem.com/).

Before other pip installs, bootstrap the selected environment with the integrity-pinned wheels:

```sh
python -m pip install --require-hashes --only-binary=:all: --no-deps -r requirements-bootstrap.txt
python -m pip install -r requirements.txt
```

The pinned bootstrap protects package integrity even when the old installer's certificate bundle is affected. It is not an operating-system trust-store update. Native Windows/macOS trust and command-line OpenSSL PEM stores may differ; follow the platform vendor's remediation for every store in use. Restart Odysseus and its subprocesses after updating trust.

On Linux/OpenSSL deployments, inspect both the effective CA file and hashed CA directory, plus the two Python bundles:

```sh
python scripts/check_ca_trust.py --system --python --overrides
```

Explicit PEM bundles can also be passed as positional arguments. The check rejects the four published root fingerprints, all sixteen published intermediate certificates (including their cross-signs), the cross-signed G3 issuer in the published test chains, and malformed/empty bundles. Checking intermediates matters because adding one as a custom trust anchor can restore an affected chain even after its roots have been removed.

`--overrides` checks every nonempty `LLM_CA_BUNDLE`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `PIP_CERT`, `NODE_EXTRA_CA_CERTS` and `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH` setting in the checker's process environment, including configured fallback settings. Requests/pip hashed-directory overrides are inspected too; `--system` covers `SSL_CERT_DIR`. Run with the application's environment and filesystem access. The script does not load `.env` or application configuration files; pass any CA paths configured only there explicitly, for example `python scripts/check_ca_trust.py --system --python /path/to/private-ca.pem`. Missing or invalid configured files fail the check. Selecting only `--overrides` with no configured paths also fails instead of reporting that stores were validated.

This is an offline inventory check of known certificate fingerprints. It does not modify stores, reject requests at runtime, model native OS revocation, or detect arbitrary reissued certificates sharing the compromised keys. Chromium's policy separately matches public keys. Check mounted or replaced CA files again after deployment, remove affected trust through the owning platform/client configuration, and restart clients that cache SSL contexts. A passing build cannot validate custom files introduced later.

Both Docker build stages refresh system CA certificates and bootstrap pip/certifi before dependency installation. The build fails if known affected CA certificates remain. Node uses the corrected system store through `--use-openssl-ca`. Python gRPC uses that same PEM file through `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH`; updating certifi alone does not replace gRPC's independent wheel bundle. After dependency installation, the image checks gRPC's selected file as well. An explicit gRPC override must be readable and free of known affected CA certificates: gRPC can otherwise fall back to its affected bundled defaults. Upstream gRPC has [merged a bundle update](https://github.com/grpc/grpc/commit/8b32af3bf498c2ba9667410eaa8c836e700e97e6); as checked on 2026-10-21, its [release backport](https://github.com/grpc/grpc/pull/43700) is still open and the latest published grpcio wheel is 1.84.0. Retain the checked override until a released replacement's actual trust behavior has been verified.

Chromium uses a separate trust store. The Docker image installs a managed `CADistrustedCertificates` policy for the eight compromised intermediate public keys, covering their cross-signs without depending on background revocation updates. It adds no trusted certificate and does not disable certificate verification. The policy and public-certificate provenance are documented in [the browser policy note](../docker/chromium-ca-policy.md). Native browser installations and independently managed profiles require their own platform policy or vendor update; this image policy does not configure host browsers.

Rebuild with a fresh base and dependency layers when remediating an existing deployment:

```sh
docker compose build --pull --no-cache odysseus
docker compose up -d odysseus
docker compose exec odysseus python scripts/check_ca_trust.py --system --python --grpc --overrides
```

SearXNG is a separate HTTPS client and image; updating the Odysseus image does not patch it. Inspect its effective CA path and update or rebuild that image independently. Also inspect persisted `/app/.local` packages, remote Cookbook environments, and externally configured MCP runtimes. Image replacement does not necessarily replace those environments.

For behavioral validation, all twelve [published test chains](https://emudhra.we-have-a-problem.com/chains.zip), including the AAA cross-signs, must fail certificate verification through the effective stores. Confirm that an ordinary known-good HTTPS request still succeeds. In Chromium, confirm the managed policy is loaded at `chrome://policy` and test the incident endpoints through the actual browser path with certificate verification enabled. The PEM checker cannot inspect Chromium's policy or its active verifier. Package versions and a successful image build alone do not prove that a running deployment selects the corrected store.
