import os
import shutil
import filecmp
from pathlib import Path

# === SETTINGS ===
SOURCE_DIR = Path("/Volumes/Creator Pro/GDrive Jul 31st")  # Where Takeout folders are
DEST_DIR = SOURCE_DIR / "Drive Combine"                    # Rebuilt structure goes here
DRY_RUN = True                                              # Set False to actually copy

# === SCAN FOR TAKEOUT FOLDERS ===
takeout_folders = sorted([f for f in SOURCE_DIR.glob("Takeout*/Drive") if f.is_dir()])

for drive_folder in takeout_folders:
    for root, dirs, files in os.walk(drive_folder):
        rel_path = Path(root).relative_to(drive_folder)
        target_dir = DEST_DIR / rel_path

        if DRY_RUN:
            print(f"[DRY-RUN] Would create folder: {target_dir}")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            src_file = Path(root) / file
            dst_file = target_dir / file

            counter = 1
            while dst_file.exists():
                if filecmp.cmp(src_file, dst_file, shallow=False):
                    break  # Identical, skip copy
                else:
                    dst_file = target_dir / f"{dst_file.stem} ({counter}){dst_file.suffix}"
                    counter += 1

            if dst_file.exists() and filecmp.cmp(src_file, dst_file, shallow=False):
                continue  # Skip identical file

            if DRY_RUN:
                print(f"[DRY-RUN] Would copy: {src_file} -> {dst_file}")
            else:
                shutil.copy2(src_file, dst_file)
                print(f"✅ Copied: {src_file} -> {dst_file}")