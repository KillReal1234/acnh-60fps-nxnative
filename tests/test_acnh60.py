"""Tests without game files: the pchtxt offset rule, the IPS reader and the NSO writer.
With NXNATIVE set to an nxnative checkout, the written NSO is also read back with nxnative's own loader.
Run: python3 -m unittest discover -s tests"""
import os, struct, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import acnh60

BID = acnh60.MAIN_BID


class Pchtxt(unittest.TestCase):
    def text(self, body, shift='0x100'):
        return f'@nsobid-{BID}\n@flag print_values\n@flag offset_shift {shift}\n{body}\n'

    def test_written_offset_is_the_image_offset_with_the_usual_shift(self):
        # the mod's first patch: its comment names image offset 374f700 (fmov s8,#1.0 -> #0.5)
        got = acnh60.pchtxt(self.text('@enabled\n0374F700 08102C1E\n@stop'))
        self.assertEqual(got, [(0x374f700, bytes.fromhex('08102C1E'))])

    def test_other_shift(self):
        self.assertEqual(acnh60.pchtxt(self.text('@enabled\n00001000 AABBCCDD', shift='0'))[0][0], 0x1000 - 0x100)

    def test_disabled_and_stop_sections_are_skipped(self):
        body = '@enabled\n00000010 00000000\n@disabled\n00000020 11111111\n@enabled\n00000030 22222222 // note\n@stop\n00000040 33333333'
        self.assertEqual([o for o, _ in acnh60.pchtxt(self.text(body))], [0x10, 0x30])

    def test_wrong_build_is_refused(self):
        with self.assertRaises(acnh60.Error):
            acnh60.pchtxt(self.text('@enabled\n00000010 00000000').replace(BID, '0' * 32))


class Ips(unittest.TestCase):
    def test_records_and_rle(self):
        patch = b'PATCH' + b'\x00\x00\x01' + b'\x00\x02' + b'\xaa\xbb' + b'\x00\x00\x05' + b'\x00\x00' + b'\x00\x03' + b'\xcc' + b'EOF'
        self.assertEqual(acnh60.ips(patch, bytes(10)), bytes.fromhex('00aabb0000cccccc0000'))

    def test_write_past_end(self):
        with self.assertRaises(acnh60.Error):
            acnh60.ips(b'PATCH' + b'\x00\x00\x09' + b'\x00\x02' + b'\x01\x02' + b'EOF', bytes(10))

    def test_not_ips(self):
        with self.assertRaises(acnh60.Error):
            acnh60.ips(b'NOPE', bytes(4))


def synthetic_nso():
    """A small NSO header and image: text 0x1000 @0, ro 0x1000 @0x1000, data 0x800 @0x2000, flags as a retail module (all compressed and hashed)"""
    h = bytearray(0x100); h[:4] = b'NSO0'; struct.pack_into('<I', h, 0xc, 0x3f)
    for i, (mo, sz) in enumerate(((0, 0x1000), (0x1000, 0x1000), (0x2000, 0x800))):
        struct.pack_into('<III', h, 0x10 + i * 0x10, 0x999, mo, sz); struct.pack_into('<I', h, 0x60 + i * 4, 0x123)
    struct.pack_into('<I', h, 0x1c, 0x100); struct.pack_into('<I', h, 0x2c, 1); struct.pack_into('<I', h, 0x3c, 0x4000)
    h[0x40:0x50] = bytes.fromhex(BID)
    image = bytearray(os.urandom(0x2800))
    return bytes(h), image


class NsoWriter(unittest.TestCase):
    def test_layout(self):
        h, image = synthetic_nso()
        out = acnh60.nso_bytes(h, image)
        self.assertEqual(struct.unpack_from('<I', out, 0xc)[0], 0)
        self.assertEqual(out[0x40:0x50], bytes.fromhex(BID))
        for i, (mo, sz) in enumerate(((0, 0x1000), (0x1000, 0x1000), (0x2000, 0x800))):
            fo, mo2, sz2 = struct.unpack_from('<III', out, 0x10 + i * 0x10)
            self.assertEqual((mo2, sz2, struct.unpack_from('<I', out, 0x60 + i * 4)[0]), (mo, sz, sz))
            self.assertEqual(out[fo:fo + sz], image[mo:mo + sz])

    @unittest.skipUnless(os.environ.get('NXNATIVE'), 'NXNATIVE not set')
    def test_nxnative_reads_it_back(self):
        nso, _ = acnh60.tools(None)
        h, image = synthetic_nso()
        m = nso.load(acnh60.nso_bytes(h, image), 'synthetic')
        self.assertEqual(bytes(m.image), bytes(image))
        self.assertEqual(m.build_id[:16].hex().upper(), BID)


if __name__ == '__main__': unittest.main()
