# acnh-frame-rate Specification

## Purpose
Lets the player run Animal Crossing: New Horizons 3.0.3, built with nxnative from their own dump, at 60 fps while the game world keeps the speed of the 30 fps original, using "ACNH 60 FPS + SpeedFix" by tmouh.

## Requirements

### Requirement: 60 fps presentation
A Mac app of Animal Crossing: New Horizons built from an extraction with the SpeedFix applied and with `env60.txt` SHALL present one new game frame per 60 Hz display refresh.

#### Scenario: Steady 60 fps on the Mac
- **WHEN** the SpeedFix Mac app runs from launch to Timmy's welcome dialogue at the Nook Inc. counter
- **THEN** the host log reports a frame time p50 of 16.67 ms and a present interval mode of `display`

### Requirement: Normal game speed at 60 fps
The game world SHALL advance at the same rate per wall-clock second as the unmodified 30 fps game, not twice as fast.

#### Scenario: Same scene at the same moment
- **WHEN** the 30 fps build and the SpeedFix build start from the same state and are captured 20 s and 30 s after launch
- **THEN** both captures show the same point of the opening, while an unlocked 60 fps build without the SpeedFix is already ahead

#### Scenario: Frame rate below 60
- **WHEN** the device cannot hold 60 fps
- **THEN** the game slows in proportion to the frame rate, as the SpeedFix scales per-update amounts

### Requirement: Matching game build only
`apply` SHALL accept only `main` build `FF1D1C05670DB6021C85B624A710B963` (version 3.0.3); any other build SHALL be refused before any file is written.

#### Scenario: Another version in the folder
- **WHEN** the extracted `main` is a build other than 3.0.3
- **THEN** `apply` exits with status 1 and an error naming the build, and the extraction is unchanged

### Requirement: Same-size parameter files
The modded parameter files (`Pack/StaticParam.pack` and the `Bcsv` tables `ItemNpcFtrActionParam`, `ItemNpcWherearenFtrActionParam`, `NpcInterest`) SHALL replace the game's files only when their sizes match the game's.

#### Scenario: Size mismatch
- **WHEN** a modded file's size differs from the game's file of the same path
- **THEN** `apply` exits with status 1 and an error naming the file and both sizes, before any file is written

### Requirement: Reversible
`apply` SHALL keep the original `main` and the original bytes of every replaced RomFS file, and `restore` SHALL put them back so the 30 fps game can be rebuilt.

#### Scenario: Restore the 30 fps game
- **WHEN** `restore` is run on a SpeedFix extraction
- **THEN** `main` and the four RomFS files have their original SHA-256s, and the saved originals are removed

#### Scenario: Applying twice
- **WHEN** `apply` is run on an extraction that already has the SpeedFix
- **THEN** `main` and `RomFS.img` are byte-identical to a single apply, since every run starts from the saved originals

### Requirement: Shared saves
The SpeedFix build SHALL use the same save location as the 30 fps build of the same title.

#### Scenario: Switching builds
- **WHEN** the player switches between the 30 fps and the SpeedFix Mac app
- **THEN** both open the save in `~/Library/Application Support/nxnative/01006F8002326000/`

### Requirement: No redistributed content
This repository SHALL contain no game files, keys, extracted data or files of tmouh's mod; the mod SHALL be fetched from its author and credited as "ACNH 60 FPS + SpeedFix by tmouh" with its link (CC BY-NC 4.0).

#### Scenario: Repository contents
- **WHEN** the repository is checked out
- **THEN** it holds only the adapter, its tests and documentation, and its README names and links the mod and its licence
