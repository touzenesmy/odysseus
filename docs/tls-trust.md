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
python scripts/check_ca_trust.py --system --python
```

Explicit PEM bundles can also be passed as positional arguments. The check rejects the incident's known root fingerprints and malformed/empty bundles. It does not model native OS intermediate revocation, custom TLS implementations, or arbitrary certificates added by an operator.

Both Docker build stages refresh system CA certificates and bootstrap pip/certifi before dependency installation. The build fails if affected roots remain. Node uses the corrected system store through `--use-openssl-ca`. Rebuild with a fresh base and dependency layers when remediating an existing deployment:

```sh
docker compose build --pull --no-cache odysseus
docker compose up -d odysseus
docker compose exec odysseus python scripts/check_ca_trust.py --system --python
```

SearXNG is a separate HTTPS client and image; updating the Odysseus image does not patch it. Inspect its effective CA path and update or rebuild that image independently. Also inspect persisted `/app/.local` packages, remote Cookbook environments, and externally configured MCP runtimes. Image replacement does not necessarily replace those environments.

For behavioral validation, all twelve [published test chains](https://emudhra.we-have-a-problem.com/chains.zip), including the AAA cross-signs, must fail certificate verification through the effective stores. Confirm that an ordinary known-good HTTPS request still succeeds. Package versions and a successful image build alone do not prove that a running deployment selects the corrected store.
