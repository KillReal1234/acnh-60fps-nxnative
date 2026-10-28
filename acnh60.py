#!/usr/bin/env python3
"""Bake "ACNH 60 FPS + SpeedFix" by tmouh into an nxnative extraction of Animal Crossing: New Horizons 3.0.3.

  acnh60.py apply   <build dir> --mod <acnh-60fps checkout> [--nxnative <nxnative checkout>]
  acnh60.py restore <build dir> [--nxnative <nxnative checkout>]

<build dir> is the NSP script's work folder, <NSP folder>/01006F8002326000_build. In its extract/v2228224/:
  ExeFS/main  becomes an uncompressed NSO with the SpeedFix words (compression and hash-check flags cleared, same build ID);
              the original is kept as ExeFS/main.orig
  RomFS.img   gets the modded Pack/StaticParam.pack (the mod's IPS over your own file) and three Bcsv tables, written in place
              (same sizes); the original bytes are kept in speedfix_orig/
Every apply starts from the saved originals, so applying twice gives the same bytes. The mod's sdk patch is not used:
nxnative draws NVN itself, and DM_PRESENT_INTERVAL=display (env60.txt, passed to the NSP script with --env-file) does its job.
nxnative's own loaders (dm/tools/nso.py, dm/tools/romfs.py) are used: --nxnative, or the NXNATIVE environment variable."""
import argparse, hashlib, os, re, shutil, struct, sys
from pathlib import Path

MAIN_BID = 'FF1D1C05670DB6021C85B624A710B963'   # main of 3.0.3 (v2228224)
VERSION_DIR = 'extract/v2228224'
MOD_DIR = 'ryujinx/mods/contents/01006F8002326000/ACNH 60 FPS + SpeedFix'
MOD_PCHTXT = 'exefs/speedfix_main.pchtxt'
MOD_PACK_IPS = 'pack/StaticParam.pack.ips'
TESTED_COMMIT = 'e5e03e64739334c9fbd36f19658b98e805f8ba8d'
ROMFS_FILES = ('Pack/StaticParam.pack', 'Bcsv/ItemNpcFtrActionParam.bcsv', 'Bcsv/ItemNpcWherearenFtrActionParam.bcsv', 'Bcsv/NpcInterest.bcsv')


class Error(Exception):
    pass


def pchtxt(text, bid=MAIN_BID):
    """[(image offset, bytes)] of the @enabled entries of an IPSwitch pchtxt for module bid.
    IPSwitch: a written offset + @flag offset_shift = the IPS offset, and IPS offsets count the 0x100-byte NSO header,
    so the image offset is written + shift - 0x100 (with the usual shift of 0x100, the written offset itself)"""
    if f'@nsobid-{bid}'.lower() not in text.lower(): raise Error(f'the patch file is not for main {bid} (3.0.3)')
    shift, on, out = 0, False, []
    for line in text.splitlines():
        line = line.split('//')[0].strip()
        if m := re.match(r'@flag offset_shift (0x[0-9a-fA-F]+|\d+)$', line): shift = int(m.group(1), 0)
        elif line == '@enabled': on = True
        elif line in ('@disabled', '@stop'): on = False
        elif on and (m := re.match(r'^([0-9A-Fa-f]{8}) ([0-9A-Fa-f]+)$', line)):
            out.append((int(m.group(1), 16) + shift - 0x100, bytes.fromhex(m.group(2))))
    if not out: raise Error('the patch file has no enabled entries')
    return out


def ips(patch, data):
    """An IPS (or IPS32) patch applied to data; a write past the end is an Error"""
    d, p = bytearray(data), bytes(patch)
    if p[:5] == b'IPS32': ow, end = 4, b'EEOF'
    elif p[:5] == b'PATCH': ow, end = 3, b'EOF'
    else: raise Error('not an IPS file')
    i = 5
    while p[i:i + len(end)] != end:
        if i + ow + 2 > len(p): raise Error('IPS file cut short')
        off = int.from_bytes(p[i:i + ow], 'big'); i += ow
        n = int.from_bytes(p[i:i + 2], 'big'); i += 2
        if n: chunk = p[i:i + n]; i += n
        else: chunk = p[i + 2:i + 3] * int.from_bytes(p[i:i + 2], 'big'); i += 3
        if off + len(chunk) > len(d): raise Error(f'IPS writes past the end of the file (at {off:#x})')
        d[off:off + len(chunk)] = chunk
    return bytes(d)


def nso_bytes(header, image):
    """An NSO with header's fields and every segment stored uncompressed from image (memory layout as the header says);
    compression and hash-check flags cleared, no module name stored, build ID kept"""
    h = bytearray(header[:0x100]); at = 0x100; body = bytearray()
    for i in range(3):
        _, mo, sz = struct.unpack_from('<III', h, 0x10 + i * 0x10)
        struct.pack_into('<I', h, 0x10 + i * 0x10, at)   # file offset
        struct.pack_into('<I', h, 0x60 + i * 4, sz)      # stored size
        body += image[mo:mo + sz]; at += sz
    struct.pack_into('<I', h, 0x0c, 0)                   # flags: nothing compressed, nothing hash-checked
    struct.pack_into('<I', h, 0x1c, 0); struct.pack_into('<I', h, 0x2c, 0)   # module name offset, size
    return bytes(h + body)


def tools(nxnative):
    root = Path(nxnative or os.environ.get('NXNATIVE') or '')
    if not (root / 'dm/tools/nso.py').is_file(): raise Error('give the nxnative checkout with --nxnative or NXNATIVE (it needs dm/tools/nso.py and romfs.py)')
    sys.path.insert(0, str(root / 'dm/tools'))
    import nso, romfs
    return nso, romfs


def rom_range(romfs, img_path, rel):
    img = romfs.Image(img_path); a, b, _, _, is_file, _ = img.entry(img.find(rel))
    if not is_file: raise Error(f'RomFS {rel} is a folder')
    return a, b


def mod_commit(mod):
    head = mod / '.git/HEAD'
    if not head.is_file(): return None
    ref = head.read_text().strip()
    if ref.startswith('ref: '):
        p = mod / '.git' / ref[5:]
        return p.read_text().strip() if p.is_file() else None
    return ref


def apply(build, mod, nxnative):
    nso, romfs = tools(nxnative)
    ex = Path(build) / VERSION_DIR; exe, orig, img_path, keep = ex / 'ExeFS/main', ex / 'ExeFS/main.orig', ex / 'RomFS.img', ex / 'speedfix_orig'
    if not exe.is_file() or not img_path.is_file(): raise Error(f'{ex} has no ExeFS/main and RomFS.img: build the game once with nxnative first')
    mod = Path(mod); mdir = mod / MOD_DIR
    if not (mdir / MOD_PCHTXT).is_file(): raise Error(f'{mod} is not an acnh-60fps checkout ({MOD_DIR}/{MOD_PCHTXT} missing)')
    if (c := mod_commit(mod)) != TESTED_COMMIT: print(f'note: the mod checkout is at {c or "an unknown commit"}, tested with {TESTED_COMMIT[:7]}')

    # check everything before writing anything
    src = (orig if orig.exists() else exe).read_bytes(); m = nso.load(src, 'main')
    if m.build_id[:16].hex().upper() != MAIN_BID: raise Error(f'main is build {m.build_id[:16].hex()}, not 3.0.3: nothing changed')
    words = pchtxt((mdir / MOD_PCHTXT).read_text())
    image = bytearray(m.image)
    for off, b in words:
        if off < 0 or off + len(b) > len(image): raise Error(f'patch at {off:#x} lies outside the module image')
        image[off:off + len(b)] = b
    new_main = nso_bytes(src, image)
    check = nso.load(new_main, 'patched main')
    if check.image != image or check.build_id != m.build_id: raise Error('the written NSO does not read back as the patched image')
    rom = {}
    with open(img_path, 'rb') as f:
        for rel in ROMFS_FILES:
            a, size = rom_range(romfs, img_path, rel)
            saved = keep / rel
            if saved.exists(): old = saved.read_bytes()
            else: f.seek(a); old = f.read(size)
            new = ips((mod / MOD_PACK_IPS).read_bytes(), old) if rel == 'Pack/StaticParam.pack' else (mdir / 'romfs' / rel).read_bytes()
            if len(new) != size: raise Error(f'RomFS {rel}: the modded file is {len(new)} bytes, the game\'s {size}; replacing in place needs the same size: nothing changed')
            rom[rel] = (a, old, new)

    # write: originals first, then the modded files
    if not orig.exists(): shutil.copyfile(exe, orig)
    tmp = exe.with_name('main.tmp'); tmp.write_bytes(new_main); tmp.replace(exe)
    print(f'main: {len(words)} words patched ({sum(m.image[o:o + len(b)] != b for o, b in words)} changed), original in {orig.name}')
    with open(img_path, 'r+b') as f:
        for rel, (a, old, new) in rom.items():
            saved = keep / rel
            if not saved.exists(): saved.parent.mkdir(parents=True, exist_ok=True); saved.write_bytes(old)
            f.seek(a); f.write(new)
            print(f'RomFS {rel}: {sum(x != y for x, y in zip(old, new))} bytes changed ({hashlib.sha256(new).hexdigest()[:12]})')
    print('done: build with build_ipa_from_nsp.py ... --env-file env60.txt')


def restore(build, nxnative):
    _, romfs = tools(nxnative)
    ex = Path(build) / VERSION_DIR; exe, orig, img_path, keep = ex / 'ExeFS/main', ex / 'ExeFS/main.orig', ex / 'RomFS.img', ex / 'speedfix_orig'
    if not orig.exists() and not keep.is_dir(): print('nothing to restore'); return
    if orig.exists(): shutil.copyfile(orig, exe); orig.unlink()
    if keep.is_dir():
        with open(img_path, 'r+b') as f:
            for p in sorted(x for x in keep.rglob('*') if x.is_file()):
                a, size = rom_range(romfs, img_path, p.relative_to(keep).as_posix())
                if p.stat().st_size != size: raise Error(f'{p}: saved {p.stat().st_size} bytes, the image holds {size}')
                f.seek(a); f.write(p.read_bytes())
        shutil.rmtree(keep)
    print('restored the original main and RomFS files: build without --env-file for 30 fps')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('apply', help='bake the 60 fps SpeedFix into the extraction'); a.add_argument('build'); a.add_argument('--mod', required=True)
    r = sub.add_parser('restore', help='put the original main and RomFS files back'); r.add_argument('build')
    for p in (a, r): p.add_argument('--nxnative')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'apply': apply(args.build, args.mod, args.nxnative)
        else: restore(args.build, args.nxnative)
    except Error as e:
        print(f'error: {e}', file=sys.stderr); return 1
    return 0


if __name__ == '__main__': sys.exit(main())
