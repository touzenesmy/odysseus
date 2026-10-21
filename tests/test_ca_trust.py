"""Offline regressions for incident roots, unaffected roots, and CA directories."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_ca_trust", ROOT / "scripts/check_ca_trust.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class CATrustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Public certificate data is embedded below. Tests create temporary
        # PEM files from these constants; no fixture contains a private key.
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixtures = Path(cls.temporary.name)
        for name, pem in PUBLIC_CERTIFICATES.items():
            (cls.fixtures / name).write_text(pem)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_unaffected_emsign_root_remains_usable(self):
        checker.check_bundle(self.fixtures / "emsign-g1.pem")

    def test_compromised_emsign_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "emSign ECC Root CA - G3"):
            checker.check_bundle(self.fixtures / "emsign-g3.pem")

    def test_aaa_cross_sign_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "AAA Certificate Services"):
            checker.check_bundle(self.fixtures / "aaa.pem")

    def test_mixed_bundle_does_not_hide_an_affected_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "mixed.pem"
            bundle.write_bytes((self.fixtures / "emsign-g1.pem").read_bytes() + (self.fixtures / "aaa.pem").read_bytes())
            with self.assertRaisesRegex(ValueError, "AAA Certificate Services"):
                checker.check_bundle(bundle)

    def test_empty_malformed_and_missing_bundles_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for content in ("", "not a certificate"):
                path = Path(tmp) / "bad.pem"
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises((ssl.SSLError, ValueError)):
                    checker.check_bundle(path)
            with self.assertRaises(OSError):
                checker.check_bundle(Path(tmp) / "missing.pem")

    def test_safe_cafile_does_not_hide_stale_hashed_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "14bc7599.0").symlink_to(self.fixtures / "emsign-g3.pem")
            defaults = ssl.get_default_verify_paths()._replace(
                cafile=str(self.fixtures / "emsign-g1.pem"), capath=str(directory)
            )
            errors = io.StringIO()
            with patch.object(checker.ssl, "get_default_verify_paths", return_value=defaults), patch.dict(
                os.environ, {defaults.openssl_capath_env: str(directory)}
            ):
                with contextlib.redirect_stderr(errors):
                    result = checker.main(["--system"])
            self.assertEqual(result, 1)
            self.assertIn("emSign ECC Root CA - G3", errors.getvalue())

    def test_multiple_ca_directories_are_all_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean, stale = Path(tmp) / "clean", Path(tmp) / "stale"
            clean.mkdir()
            stale.mkdir()
            (stale / "ee64a828.0").symlink_to(self.fixtures / "aaa.pem")
            defaults = ssl.get_default_verify_paths()._replace(
                cafile=str(self.fixtures / "emsign-g1.pem"), capath=None
            )
            errors = io.StringIO()
            with patch.object(checker.ssl, "get_default_verify_paths", return_value=defaults), patch.dict(
                os.environ, {defaults.openssl_capath_env: os.pathsep.join(map(str, (clean, stale)))}
            ):
                with contextlib.redirect_stderr(errors):
                    result = checker.main(["--system"])
            self.assertEqual(result, 1)
            self.assertIn("AAA Certificate Services", errors.getvalue())


# Public Mozilla CA certificates; provenance: tests/fixtures/ca-trust/README.md.
PUBLIC_CERTIFICATES = {
    'aaa.pem': """-----BEGIN CERTIFICATE-----
MIIEMjCCAxqgAwIBAgIBATANBgkqhkiG9w0BAQUFADB7MQswCQYDVQQGEwJHQjEb
MBkGA1UECAwSR3JlYXRlciBNYW5jaGVzdGVyMRAwDgYDVQQHDAdTYWxmb3JkMRow
GAYDVQQKDBFDb21vZG8gQ0EgTGltaXRlZDEhMB8GA1UEAwwYQUFBIENlcnRpZmlj
YXRlIFNlcnZpY2VzMB4XDTA0MDEwMTAwMDAwMFoXDTI4MTIzMTIzNTk1OVowezEL
MAkGA1UEBhMCR0IxGzAZBgNVBAgMEkdyZWF0ZXIgTWFuY2hlc3RlcjEQMA4GA1UE
BwwHU2FsZm9yZDEaMBgGA1UECgwRQ29tb2RvIENBIExpbWl0ZWQxITAfBgNVBAMM
GEFBQSBDZXJ0aWZpY2F0ZSBTZXJ2aWNlczCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBAL5AnfRu4ep2hxxNRUSOvkbIgwadwSr+GB+O5AL686tdUIoWMQua
BtDFcCLNSS1UY8y2bmhGC1Pqy0wkwLxyTurxFa70VJoSCsN6sjNg4tqJVfMiWPPe
3M/vg4aijJRPn2jymJBGhCfHdr/jzDUsi14HZGWCwEiwqJH5YZ92IFCokcdmtet4
YgNW8IoaE+oxox6gmf049vYnMlhvB/VruPsUK6+3qszWY19zjNoFmag4qMsXeDZR
rOme9Hg6jc8P2ULimAyrL58OAd7vn5lJ8S3frHRNG5i1R8XlKdH5kBjHYpy+g8cm
ez6KJcfA3Z3mNWgQIJ2P2N7Sw4ScDV7oL8kCAwEAAaOBwDCBvTAdBgNVHQ4EFgQU
oBEKIz6W8Qfs4q8p74Klf9AwpLQwDgYDVR0PAQH/BAQDAgEGMA8GA1UdEwEB/wQF
MAMBAf8wewYDVR0fBHQwcjA4oDagNIYyaHR0cDovL2NybC5jb21vZG9jYS5jb20v
QUFBQ2VydGlmaWNhdGVTZXJ2aWNlcy5jcmwwNqA0oDKGMGh0dHA6Ly9jcmwuY29t
b2RvLm5ldC9BQUFDZXJ0aWZpY2F0ZVNlcnZpY2VzLmNybDANBgkqhkiG9w0BAQUF
AAOCAQEACFb8AvCb6P+k+tZ7xkSAzk/ExfYAWMymtrwUSWgEdujm7l3sAg9g1o1Q
GE8mTgHj5rCl7r+8dFRBv/38ErjHT1r0iWAFf2C3BUrz9vHCv8S5dIa2LX1rzNLz
Rt0vxuBqw8M0Ayx9lt1awg6nCpnBBYurDC/zXDrPbDdVCYfeU0BsWO/8tqtlbgT2
G9w84FoVxp7Z8VlIMCFlA2zs6SFz7JsDoeA3raAVGI/6ugLOpyypEBMs1OUIJqsi
l2D4kF501KKaU73yqWjgom7C12yxow+ev+to51byrvLjKzg6CYG1a4XXvi3tPxq3
smPi9WIsgtRqAEFQ8TmDn5XpNpaYbg==
-----END CERTIFICATE-----
""",
    'emsign-g1.pem': """-----BEGIN CERTIFICATE-----
MIIDlDCCAnygAwIBAgIKMfXkYgxsWO3W2DANBgkqhkiG9w0BAQsFADBnMQswCQYD
VQQGEwJJTjETMBEGA1UECxMKZW1TaWduIFBLSTElMCMGA1UEChMcZU11ZGhyYSBU
ZWNobm9sb2dpZXMgTGltaXRlZDEcMBoGA1UEAxMTZW1TaWduIFJvb3QgQ0EgLSBH
MTAeFw0xODAyMTgxODMwMDBaFw00MzAyMTgxODMwMDBaMGcxCzAJBgNVBAYTAklO
MRMwEQYDVQQLEwplbVNpZ24gUEtJMSUwIwYDVQQKExxlTXVkaHJhIFRlY2hub2xv
Z2llcyBMaW1pdGVkMRwwGgYDVQQDExNlbVNpZ24gUm9vdCBDQSAtIEcxMIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAk0u76WaK7p1b1TST0Bsew+eeuGQz
f2N4aLTNLnF115sgxk0pvLZoYIr3IZpWNVrzdr3YzZr/k1ZLpVkGoZM0Kd0WNHVO
8oG0x5ZOrRkVUkr+PHB1cM2vK6sVmjM8qrOLqs1D/fXqcP/tzxE7lM5OMhbTI0Aq
d7OvPAEsbO2ZLIvZTmmYsvePQbAyeGHWDV/D+qJAkh1cF+ZwPjXnorfCYuKrpDhM
tTk1b+oDafo6VGiFbdbyL0NVHpENDtjVaqSW0RM8LHhQ6DqS0hdW5TUaQBw+jSzt
Od9C4INBdN+jzcKGYEho42kLVACL5HZpIQ15TjQIXhTCzLG3rdd8cIrHhQIDAQAB
o0IwQDAdBgNVHQ4EFgQU++8Nhp6w492pufEhF38+/PB3KxowDgYDVR0PAQH/BAQD
AgEGMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAFn/8oz1h31x
PaOfG1vR2vjTnGs2vZupYeveFix0PZ7mddrXuqe8QhfnPZHr5X3dPpzxz5KsbEjM
wiI/aTvFthUvozXGaCocV685743QNcMYDHsAVhzNixl03r4PEuDQqqE/AjSxcM6d
GNYIAwlG7mDgfrbESQRRfXBgvKqy/3lyeqYdPV8q+Mri/Tm3R7nrft8EI6/6nAYH
6ftjk4BAtcZsCjEozgyfz7MjNYBBjWzEN3uBL4ChQEKF6dk4jeihU80Bv2noWgby
RQuQ+q7hv53yrlc8pa6yVvSLZUDp/TGBLPQ5Cdjua6e0ph0VpZj3AYHYhX3zUVxx
iN66zB+Afko=
-----END CERTIFICATE-----
""",
    'emsign-g3.pem': """-----BEGIN CERTIFICATE-----
MIICTjCCAdOgAwIBAgIKPPYHqWhwDtqLhDAKBggqhkjOPQQDAzBrMQswCQYDVQQG
EwJJTjETMBEGA1UECxMKZW1TaWduIFBLSTElMCMGA1UEChMcZU11ZGhyYSBUZWNo
bm9sb2dpZXMgTGltaXRlZDEgMB4GA1UEAxMXZW1TaWduIEVDQyBSb290IENBIC0g
RzMwHhcNMTgwMjE4MTgzMDAwWhcNNDMwMjE4MTgzMDAwWjBrMQswCQYDVQQGEwJJ
TjETMBEGA1UECxMKZW1TaWduIFBLSTElMCMGA1UEChMcZU11ZGhyYSBUZWNobm9s
b2dpZXMgTGltaXRlZDEgMB4GA1UEAxMXZW1TaWduIEVDQyBSb290IENBIC0gRzMw
djAQBgcqhkjOPQIBBgUrgQQAIgNiAAQjpQy4LRL1KPOxst3iAhKAnjlfSU2fySU0
WXTsuwYc58Byr+iuL+FBVIcUqEqy6HyC5ltqtdyzdc6LBtCGI79G1Y4PPwT01xyS
fvalY8L1X44uT6EYGQIrMgqCZH0Wk9GjQjBAMB0GA1UdDgQWBBR8XQKEE9TMipuB
zhccLikenEhjQjAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB/zAKBggq
hkjOPQQDAwNpADBmAjEAvvNhzwIQHWSVB7gYboiFBS+DCBeQyh+KTOgNG3qxrdWB
CUfvO6wIBHxcmbHtRwfSAjEAnbpV/KlK6O3t5nYBQnvI+GDZjVGLVTv7jHvrZQnD
+JbNR6iC8hZVdyR+EhCVBCyj
-----END CERTIFICATE-----
""",
}


if __name__ == "__main__":
    unittest.main()
