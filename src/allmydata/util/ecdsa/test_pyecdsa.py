import unittest
import time
from binascii import hexlify, unhexlify

from keys import SigningKey, VerifyingKey
from keys import BadSignatureError
import util
from util import sig_to_der, sig_to_strings
from util import infunc_strings, infunc_der
from curves import Curve, UnknownCurveError
from curves import NIST192p, NIST224p, NIST256p, NIST384p, NIST521p
import der

BENCH = False

class ECDSA(unittest.TestCase):
    def test_basic(self):
        priv = SigningKey.generate()
        pub = priv.get_verifying_key()

        data = "blahblah"
        sig = priv.sign(data)

        self.failUnless(pub.verify(sig, data))
        self.failUnlessRaises(BadSignatureError, pub.verify, sig, data+"bad")

        pub2 = VerifyingKey.from_string(pub.to_string())
        self.failUnless(pub2.verify(sig, data))

    def test_lengths(self):
        default = NIST192p
        priv = SigningKey.generate()
        pub = priv.get_verifying_key()
        self.failUnlessEqual(len(pub.to_string()), default.verifying_key_length)
        sig = priv.sign("data")
        self.failUnlessEqual(len(sig), default.signature_length)
        if BENCH:
            print
        for curve in (NIST192p, NIST224p, NIST256p, NIST384p, NIST521p):
            start = time.time()
            priv = SigningKey.generate(curve=curve)
            pub1 = priv.get_verifying_key()
            keygen_time = time.time() - start
            pub2 = VerifyingKey.from_string(pub1.to_string(), curve)
            self.failUnlessEqual(pub1.to_string(), pub2.to_string())
            self.failUnlessEqual(len(pub1.to_string()),
                                 curve.verifying_key_length)
            start = time.time()
            sig = priv.sign("data")
            sign_time = time.time() - start
            self.failUnlessEqual(len(sig), curve.signature_length)
            if BENCH:
                start = time.time()
                pub1.verify(sig, "data")
                verify_time = time.time() - start
                print "%s: siglen=%d, keygen=%0.3fs, sign=%0.3f, verify=%0.3f" \
                      % (curve.name, curve.signature_length,
                         keygen_time, sign_time, verify_time)

    def test_serialize(self):
        seed = "secret"
        data = "data"
        priv1 = SigningKey.from_seed(seed)
        priv2 = SigningKey.from_seed(seed)
        pub1 = priv1.get_verifying_key()
        pub2 = priv2.get_verifying_key()
        sig1 = priv1.sign(data)
        sig2 = priv2.sign(data)
        self.failUnless(pub1.verify(sig1, data))
        self.failUnless(pub2.verify(sig1, data))
        self.failUnless(pub1.verify(sig2, data))
        self.failUnless(pub2.verify(sig2, data))
        self.failUnlessEqual(hexlify(pub1.to_string()),
                             hexlify(pub2.to_string()))

    def test_nonrandom(self):
        s = "all the entropy in the entire world, compressed into one line"
        def not_much_entropy(numbytes):
            return s[:numbytes]
        # we control the entropy source, these two keys should be identical:
        priv1 = SigningKey.generate(entropy=not_much_entropy)
        priv2 = SigningKey.generate(entropy=not_much_entropy)
        self.failUnlessEqual(hexlify(priv1.get_verifying_key().to_string()),
                             hexlify(priv2.get_verifying_key().to_string()))
        # likewise, signatures should be identical. Obviously you'd never
        # want to do this with keys you care about, because the secrecy of
        # the private key depends upon using different random numbers for
        # each signature
        sig1 = priv1.sign("data", entropy=not_much_entropy)
        sig2 = priv2.sign("data", entropy=not_much_entropy)
        self.failUnlessEqual(hexlify(sig1), hexlify(sig2))

    def failUnlessPrivkeysEqual(self, priv1, priv2):
        self.failUnlessEqual(priv1.privkey.secret_multiplier,
                             priv2.privkey.secret_multiplier)
        self.failUnlessEqual(priv1.privkey.public_key.generator,
                             priv2.privkey.public_key.generator)

    def failIfPrivkeysEqual(self, priv1, priv2):
        self.failIfEqual(priv1.privkey.secret_multiplier,
                         priv2.privkey.secret_multiplier)

    def test_privkey_creation(self):
        s = "all the entropy in the entire world, compressed into one line"
        def not_much_entropy(numbytes):
            return s[:numbytes]
        priv1 = SigningKey.generate()
        self.failUnlessEqual(priv1.baselen, NIST192p.baselen)

        priv1 = SigningKey.generate(curve=NIST224p)
        self.failUnlessEqual(priv1.baselen, NIST224p.baselen)

        priv1 = SigningKey.generate(entropy=not_much_entropy)
        self.failUnlessEqual(priv1.baselen, NIST192p.baselen)
        priv2 = SigningKey.generate(entropy=not_much_entropy)
        self.failUnlessEqual(priv2.baselen, NIST192p.baselen)
        self.failUnlessPrivkeysEqual(priv1, priv2)

        priv1 = SigningKey.from_seed(seed="no_entropy")
        self.failUnlessEqual(priv1.baselen, NIST192p.baselen)
        priv2 = SigningKey.from_seed(seed="no_entropy")
        self.failUnlessPrivkeysEqual(priv1, priv2)

        priv1 = SigningKey.from_seed(seed="no_entropy", curve=NIST224p)
        self.failUnlessEqual(priv1.baselen, NIST224p.baselen)

        priv1 = SigningKey.from_seed(seed="different")
        priv2 = SigningKey.from_seed(seed="than you")
        self.failIfPrivkeysEqual(priv1, priv2)

        priv1 = SigningKey.from_secret_exponent(secexp=3)
        self.failUnlessEqual(priv1.baselen, NIST192p.baselen)
        priv2 = SigningKey.from_secret_exponent(secexp=3)
        self.failUnlessPrivkeysEqual(priv1, priv2)

        priv1 = SigningKey.from_secret_exponent(secexp=4, curve=NIST224p)
        self.failUnlessEqual(priv1.baselen, NIST224p.baselen)

    def test_privkey_strings(self):
        priv1 = SigningKey.generate()
        s1 = priv1.to_string()
        self.failUnlessEqual(type(s1), str)
        self.failUnlessEqual(len(s1), NIST192p.baselen)
        priv2 = SigningKey.from_string(s1)
        self.failUnlessPrivkeysEqual(priv1, priv2)

        s1 = priv1.to_pem()
        self.failUnlessEqual(type(s1), str)
        self.failUnless(s1.startswith("-----BEGIN EC PRIVATE KEY-----"))
        self.failUnless(s1.strip().endswith("-----END EC PRIVATE KEY-----"))
        priv2 = SigningKey.from_pem(s1)
        self.failUnlessPrivkeysEqual(priv1, priv2)

        s1 = priv1.to_der()
        self.failUnlessEqual(type(s1), str)
        priv2 = SigningKey.from_der(s1)
        self.failUnlessPrivkeysEqual(priv1, priv2)

        priv1 = SigningKey.generate(curve=NIST256p)
        s1 = priv1.to_pem()
        self.failUnlessEqual(type(s1), str)
        self.failUnless(s1.startswith("-----BEGIN EC PRIVATE KEY-----"))
        self.failUnless(s1.strip().endswith("-----END EC PRIVATE KEY-----"))
        priv2 = SigningKey.from_pem(s1)
        self.failUnlessPrivkeysEqual(priv1, priv2)

        s1 = priv1.to_der()
        self.failUnlessEqual(type(s1), str)
        priv2 = SigningKey.from_der(s1)
        self.failUnlessPrivkeysEqual(priv1, priv2)

    def failUnlessPubkeysEqual(self, pub1, pub2):
        self.failUnlessEqual(pub1.pubkey.point, pub2.pubkey.point)
        self.failUnlessEqual(pub1.pubkey.generator, pub2.pubkey.generator)
        self.failUnlessEqual(pub1.curve, pub2.curve)

    def test_pubkey_strings(self):
        priv1 = SigningKey.generate()
        pub1 = priv1.get_verifying_key()
        s1 = pub1.to_string()
        self.failUnlessEqual(type(s1), str)
        self.failUnlessEqual(len(s1), NIST192p.verifying_key_length)
        pub2 = VerifyingKey.from_string(s1)
        self.failUnlessPubkeysEqual(pub1, pub2)

        priv1 = SigningKey.generate(curve=NIST256p)
        pub1 = priv1.get_verifying_key()
        s1 = pub1.to_string()
        self.failUnlessEqual(type(s1), str)
        self.failUnlessEqual(len(s1), NIST256p.verifying_key_length)
        pub2 = VerifyingKey.from_string(s1, curve=NIST256p)
        self.failUnlessPubkeysEqual(pub1, pub2)

        pub1_der = pub1.to_der()
        self.failUnlessEqual(type(pub1_der), str)
        pub2 = VerifyingKey.from_der(pub1_der)
        self.failUnlessPubkeysEqual(pub1, pub2)

        self.failUnlessRaises(der.UnexpectedDER,
                              VerifyingKey.from_der, pub1_der+"junk")
        badpub = VerifyingKey.from_der(pub1_der)
        class FakeGenerator:
            def order(self): return 123456789
        badcurve = Curve("unknown", None, FakeGenerator(), (1,2,3,4,5,6))
        badpub.curve = badcurve
        badder = badpub.to_der()
        self.failUnlessRaises(UnknownCurveError, VerifyingKey.from_der, badder)

        pem = pub1.to_pem()
        self.failUnlessEqual(type(pem), str)
        self.failUnless(pem.startswith("-----BEGIN PUBLIC KEY-----"), pem)
        self.failUnless(pem.strip().endswith("-----END PUBLIC KEY-----"), pem)
        pub2 = VerifyingKey.from_pem(pem)
        self.failUnlessPubkeysEqual(pub1, pub2)

    def test_signature_strings(self):
        priv1 = SigningKey.generate()
        pub1 = priv1.get_verifying_key()
        data = "data"

        sig = priv1.sign(data)
        self.failUnlessEqual(type(sig), str)
        self.failUnlessEqual(len(sig), NIST192p.signature_length)
        self.failUnless(pub1.verify(sig, data))

        sig = priv1.sign(data, outfunc=sig_to_strings)
        self.failUnlessEqual(type(sig), tuple)
        self.failUnlessEqual(len(sig), 2)
        self.failUnlessEqual(type(sig[0]), str)
        self.failUnlessEqual(type(sig[1]), str)
        self.failUnlessEqual(len(sig[0]), NIST192p.baselen)
        self.failUnlessEqual(len(sig[1]), NIST192p.baselen)
        self.failUnless(pub1.verify(sig, data, infunc=infunc_strings))

        sig_der = priv1.sign(data, outfunc=sig_to_der)
        self.failUnlessEqual(type(sig_der), str)
        self.failUnless(pub1.verify(sig_der, data, infunc=infunc_der))


class DER(unittest.TestCase):
    def test_oids(self):
        oid_ecPublicKey = der.encode_oid(1, 2, 840, 10045, 2, 1)
        self.failUnlessEqual(hexlify(oid_ecPublicKey), "06072a8648ce3d0201")
        self.failUnlessEqual(hexlify(NIST224p.encoded_oid), "06052b81040021")
        self.failUnlessEqual(hexlify(NIST256p.encoded_oid),
                             "06082a8648ce3d030107")
        x = oid_ecPublicKey + "more"
        x1, rest = der.remove_object(x)
        self.failUnlessEqual(x1, (1, 2, 840, 10045, 2, 1))
        self.failUnlessEqual(rest, "more")

    def test_integer(self):
        self.failUnlessEqual(der.encode_integer(0), "\x02\x01\x00")
        self.failUnlessEqual(der.encode_integer(1), "\x02\x01\x01")
        self.failUnlessEqual(der.encode_integer(127), "\x02\x01\x7f")
        self.failUnlessEqual(der.encode_integer(128), "\x02\x02\x00\x80")
        self.failUnlessEqual(der.encode_integer(256), "\x02\x02\x01\x00")
        #self.failUnlessEqual(der.encode_integer(-1), "\x02\x01\xff")

        def s(n): return der.remove_integer(der.encode_integer(n) + "junk")
        self.failUnlessEqual(s(0), (0, "junk"))
        self.failUnlessEqual(s(1), (1, "junk"))
        self.failUnlessEqual(s(127), (127, "junk"))
        self.failUnlessEqual(s(128), (128, "junk"))
        self.failUnlessEqual(s(256), (256, "junk"))
        self.failUnlessEqual(s(1234567890123456789012345678901234567890),
                             ( 1234567890123456789012345678901234567890,"junk"))

    def test_number(self):
        self.failUnlessEqual(der.encode_number(0), "\x00")
        self.failUnlessEqual(der.encode_number(127), "\x7f")
        self.failUnlessEqual(der.encode_number(128), "\x81\x00")
        self.failUnlessEqual(der.encode_number(3*128+7), "\x83\x07")
        #self.failUnlessEqual(der.read_number("\x81\x9b"+"more"), (155, 2))
        #self.failUnlessEqual(der.encode_number(155), "\x81\x9b")
        for n in (0, 1, 2, 127, 128, 3*128+7, 840, 10045): #, 155):
            x = der.encode_number(n) + "more"
            n1, llen = der.read_number(x)
            self.failUnlessEqual(n1, n)
            self.failUnlessEqual(x[llen:], "more")

    def test_length(self):
        self.failUnlessEqual(der.encode_length(0), "\x00")
        self.failUnlessEqual(der.encode_length(127), "\x7f")
        self.failUnlessEqual(der.encode_length(128), "\x81\x80")
        self.failUnlessEqual(der.encode_length(255), "\x81\xff")
        self.failUnlessEqual(der.encode_length(256), "\x82\x01\x00")
        self.failUnlessEqual(der.encode_length(3*256+7), "\x82\x03\x07")
        self.failUnlessEqual(der.read_length("\x81\x9b"+"more"), (155, 2))
        self.failUnlessEqual(der.encode_length(155), "\x81\x9b")
        for n in (0, 1, 2, 127, 128, 255, 256, 3*256+7, 155):
            x = der.encode_length(n) + "more"
            n1, llen = der.read_length(x)
            self.failUnlessEqual(n1, n)
            self.failUnlessEqual(x[llen:], "more")

    def test_sequence(self):
        x = der.encode_sequence("ABC", "DEF") + "GHI"
        self.failUnlessEqual(x, "\x30\x06ABCDEFGHI")
        x1, rest = der.remove_sequence(x)
        self.failUnlessEqual(x1, "ABCDEF")
        self.failUnlessEqual(rest, "GHI")

    def test_constructed(self):
        x = der.encode_constructed(0, NIST224p.encoded_oid)
        self.failUnlessEqual(hexlify(x), "a007" + "06052b81040021")
        x = der.encode_constructed(1, unhexlify("0102030a0b0c"))
        self.failUnlessEqual(hexlify(x), "a106" + "0102030a0b0c")

class Util(unittest.TestCase):
    def test_trytryagain(self):
        for i in range(1000):
            seed = "seed-%d" % i
            for order in (2**8-2, 2**8-1, 2**8, 2**8+1, 2**8+2,
                          2**16-1, 2**16+1):
                n = util.string_to_randrange_trytryagain(seed, order)
                self.failUnless(1 <= n < order, (1, n, order))

    def OFF_test_prove_uniformity(self):
        order = 2**8-2
        counts = dict([(i, 0) for i in range(1, order)])
        assert 0 not in counts
        assert order not in counts
        for i in range(1000000):
            seed = "seed-%d" % i
            n = util.string_to_randrange_trytryagain(seed, order)
            counts[n] += 1
        # this technique should use the full range
        self.failUnless(counts[order-1])
        for i in range(1, order):
            print "%3d: %s" % (i, "*"*(counts[i]/100))


if __name__ == "__main__":
    unittest.main()
