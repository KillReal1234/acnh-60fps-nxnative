# acnh-60fps-nxnative

Animal Crossing: New Horizons 3.0.3 at **60 fps with normal game speed** in [nxnative](https://github.com/seedds/nxnative), the project that runs Switch games natively on the Mac and iPhone.

The game logic and every rescaled value come from **"ACNH 60 FPS + SpeedFix" by tmouh** ([GameBanana](https://gamebanana.com/mods/722295), [GitHub](https://github.com/tmouh/acnh-60fps)). This repository is only the adapter that bakes that mod into an nxnative build. It contains no game files, no keys and none of tmouh's patches. You fetch the mod from its author.

## Why a plain unlock is not enough

Animal Crossing advances its world one fixed step per frame. nxnative can present every display refresh (`DM_PRESENT_INTERVAL=display`), and the game then runs at 60 fps at double speed. In captures taken 20 s after launch, the unlocked build was already in Timmy's dialogue while the 30 fps build was still at the counter. The game has no single time step to scale. tmouh's SpeedFix rescales each per-update amount instead: 6,417 code and data words of `main`, 1,437 values in `StaticParam.pack` and three villager tables, each checked against the 30 fps game.

## What you need

- A working nxnative setup that has already built the game once from **your own dump** of version **3.0.3** (`main` build `FF1D1C05670DB6021C85B624A710B963`), so that `<NSP folder>/01006F8002326000_build/extract/v2228224/` exists.
- Python 3.12+ (nxnative's own; the script uses its `dm/tools/nso.py` and `romfs.py`).
- git.

## Use

```bash
# 1. the mod, at the commit this adapter was tested with
git clone https://github.com/tmouh/acnh-60fps
git -C acnh-60fps checkout e5e03e64739334c9fbd36f19658b98e805f8ba8d

# 2. bake it into the extraction (keeps the originals)
python3 acnh60.py apply ~/Games/AnimalCrossing/01006F8002326000_build --mod acnh-60fps --nxnative ~/nxnative

# 3. build the Mac app with every refresh presented
python3 ~/nxnative/scripts/build_ipa_from_nsp.py ~/Games/AnimalCrossing -k ~/.switch/prod.keys \
    --platform mac-app --env-file env60.txt
```

Step 3 re-runs only the rewrite and the shader split, about 2.5 min on an M-series Mac; the extraction and the shaders are reused.

**Back to 30 fps:** `python3 acnh60.py restore <build dir> --nxnative ~/nxnative`, then build without `--env-file`.

**After a re-extraction** (`--no-keep-extracted`, a deleted `extract/`), the 30 fps files are back. Run `apply` again before building.

## What `apply` does

- `ExeFS/main` becomes an uncompressed NSO with the SpeedFix words. The compression and hash-check flags are cleared and the build ID is kept, so nxnative's profile for 3.0.3 still matches. The original is kept as `ExeFS/main.orig`.
- `Pack/StaticParam.pack` (the mod's IPS applied to your own file) and the three `Bcsv` tables are written in place inside `RomFS.img`, at the same sizes. Their original bytes are kept in `speedfix_orig/`.
- Before writing anything, it checks the `main` build, the mod files, that every patch lies inside the module and that every replaced file keeps its size.
- Every `apply` starts from the saved originals, so applying twice gives the same bytes.
- The mod's `sdk` patch is not used: nxnative draws NVN itself, and `DM_PRESENT_INTERVAL=display` in `env60.txt` does that job.

A note for anyone porting IPSwitch patches: `@flag offset_shift 0x100` means a written offset + 0x100 is the IPS offset, and IPS offsets count the 0x100-byte NSO header. So the written offset **is** the image offset. Subtracting the shift moves every word 0x100 bytes early. Here that put 28 words on relocated pointer slots, and the game crashed in its constructors at pc=0.

## Verified

On an Apple silicon Mac with macOS 27.2, Xcode 27.1 and nxnative at `a3d603a`:

- 60 fps: frame time p50 16.67 ms and p95 about 17.1 ms up to frame 4,200, no crash.
- Game speed: captures 20 s and 30 s after launch show the same moments of the opening as the unmodified 30 fps build (the Nook Inc. counter, Timmy's welcome).
- `restore` gives `main` and the four RomFS files back with their original SHA-256s.
- A `main` of another build is refused with nothing written.
- `python3 -m unittest discover -s tests`: the pchtxt offset rule, the IPS reader and the NSO writer, without game files. With `NXNATIVE` set, the written NSO is also read back with nxnative's loader.

Not verified yet: long play on the island, and the iPhone (IPA) build.

## Limits

- The game's speed still follows the frame rate: below 60 fps it slows in step. The Mac holds 60. An iPhone may drop under it when it gets hot.
- A few actions remain a fraction of a second off. See the mod's [`docs/measured.md`](https://github.com/tmouh/acnh-60fps/blob/main/docs/measured.md).
- Saves are shared with the 30 fps build: same title, same save folder.
- Only 3.0.3. The mod also covers 3.0.0 to 3.0.2, but nxnative's profile is registered for 3.0.3.

## Credits and licences

- **ACNH 60 FPS + SpeedFix by tmouh**, https://gamebanana.com/mods/722295, licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). It is used unchanged, fetched from its own repository, not redistributed here. Non-commercial use only.
- [nxnative](https://github.com/seedds/nxnative) by seedds.
- This adapter (`acnh60.py`, `tests/`, `env60.txt`, the docs): MIT, see [LICENSE](LICENSE).
- Animal Crossing is Nintendo's. This project is not affiliated with Nintendo, tmouh or nxnative. Play only games you own.

The behaviour contract is in [openspec/specs/acnh-frame-rate/spec.md](openspec/specs/acnh-frame-rate/spec.md), the design decisions in [docs/design.md](docs/design.md).
