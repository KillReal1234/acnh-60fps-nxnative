# Design

## Context

See the README, "Why a plain unlock is not enough". Constraints that shape the approach:

- nxnative packs from `<NSP folder>/<id>_build/extract/<version>/`: `ExeFS/main` (an NSO) goes through the rewriter (`patch_nso.py`), `RomFS.img` (a `DMROMFS1` image) is streamed into the app. A repeat build reuses each stage whose inputs did not change; the extraction itself is reused without re-hashing.
- The mod targets main build `FF1D1C05670DB6021C85B624A710B963` (3.0.3) and sdk `A226048605D3597F90CB1067D141CD36`, the builds the profile `01006F8002326000` registers.
- `main` relocates through RELA and RELR tables (373,225 RELR slots); `init_array` holds 8,748 constructors.

## Goals / Non-Goals

**Goals:**
- Same build pipeline and app as the 30 fps build; one extra script run before it.
- Reversible: the original bytes are kept and restored by the same script.

**Non-Goals:**
- An nxnative `FRAME_STEP` or profile change (no general time step exists in this game; the mod is per-value).
- The iPhone IPA (a follow-up change: same extraction, plus the thermal behaviour at 60 fps).
- The mod's 45 and 120 fps variants (untested with nxnative).

## Decisions

1. **Patch the extraction, not the rewriter.** The script writes the modded `main` over `ExeFS/main` and lets the rewriter run on it. Alternative: translate 6,417 words into the profile's `patches.py` `CUTS`; rejected, as `CUTS` are build-keyed code cuts in a committed file, and the mod's licence and data-segment words do not fit there.
2. **Uncompressed NSO with check flags cleared.** The modded `main` is written with every segment stored uncompressed and the compression and hash-check flags at +0x0c cleared, module name fields (+0x1c, +0x2c) zeroed; the build ID is kept, so the profile still matches. `nso.py` accepts such a module, as Horizon does.
3. **IPSwitch offsets are image offsets.** A pchtxt `@flag offset_shift 0x100` means written offset + 0x100 = IPS offset, and IPS offsets count the 0x100-byte NSO header; so image offset = written + shift - 0x100. The first attempt subtracted the shift: all words landed 0x100 early, 28 of them over RELR pointer slots, and the game crashed in `init_array` at pc=0. Check: image word `0x374f700` changes `fmov s8,#1.0` (`1e2e1008`) to `fmov s8,#0.5` (`1e2c1008`), the model animation step the mod's first comment names.
4. **RomFS files replaced in place.** The modded `StaticParam.pack` (the mod's IPS over the user's own file) and the three `Bcsv` tables have the game's sizes, so their bytes are overwritten inside `RomFS.img`; the image index stays valid and the files reach both the Mac app and a future IPA. Alternative: `DM_ROMFS_OVERLAY`; rejected, as it is a run-time host path, not packed into the app.
5. **Host present switch instead of the mod's sdk patch.** `DM_PRESENT_INTERVAL=display` (one frame per 60 Hz tick whatever interval the game sets) via `--env-file`, baked into `Contents/Resources/dm/env.txt`.

## Risks / Trade-offs

- [Below 60 fps the game slows in step: the mod fixes speed per update, not per second] → the Mac holds 60 (frame time p50 16.67 ms, p95 17.1 ms); on an iPhone, heat lowers it (handled in the IPA change).
- [A re-extraction (`--no-keep-extracted`, a new version, a deleted `extract/`) silently restores the 30 fps files] → run `acnh60.py apply` again before building; the script always starts from the saved originals.
- [The mod is a third-party, per-value patch; a few actions remain a fraction of a second off (the mod's `docs/measured.md`)] → accepted.
- [Only the first ~70 s were checked on the Mac (the Nook Inc. counter and Timmy's dialogue)] → gameplay on the island to be checked by the player.

## Migration Plan

Apply: `acnh60.py apply <build dir> --mod <mod checkout>`, then `build_ipa_from_nsp.py … --platform mac-app --env-file env60.txt`.
Rollback: `acnh60.py restore <build dir>`, then rebuild without `--env-file`.

## Open Questions

- Does a 30 fps island save behave the same after moving to the 60 fps build and back? (The save format is unchanged; untested.)
