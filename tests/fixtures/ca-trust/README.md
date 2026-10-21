# CA trust regression fixtures

The public CA certificates embedded in `tests/test_ca_trust.py` exercise the October 2026 eMudhra trust-store check. They contain no private keys. `emsign-g3.pem` and `aaa.pem` are the incident's affected trust anchors; `emsign-g1.pem` is an unaffected emSign anchor that must remain usable. The test creates temporary PEM files from these public constants. The certificate fingerprints are the factual identity of each fixture.

Sources: the [incident root list](https://emudhra.we-have-a-problem.com/roots.json) and the public Mozilla root certificates distributed in Debian's `ca-certificates` package. Behavioral chain verification should also cover the incident site's separate [twelve published server chains](https://emudhra.we-have-a-problem.com/chains.zip).
