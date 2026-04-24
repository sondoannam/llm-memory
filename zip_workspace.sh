#!/bin/bash

# Target zip file name
ZIP_NAME="track-3-day2-DoanNamSon-2A202600045.zip"

echo "Building zip archive: ${ZIP_NAME}..."

# Remove old zip if it exists
rm -f "$ZIP_NAME"

# We use git ls-files to safely get all tracked and untracked files
# while inherently respecting .gitignore rules.
# -c : cached (tracked files)
# -o : others (untracked files)
# --exclude-standard : apply standard git ignore rules
# -z : null-separated output (safe for filenames with spaces)
git ls-files -z -c -o --exclude-standard | xargs -0 zip "$ZIP_NAME"

echo "Done! Archive saved to ${ZIP_NAME}"
