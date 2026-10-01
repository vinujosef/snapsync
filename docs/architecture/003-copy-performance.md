# Copy performance investigation

## Findings (2026-10-01)

The copy action previously called `build_hash_index(destination_folder)` before
processing any source files. That function recursively read every destination
file in full to calculate SHA-256. The amount of startup I/O therefore depended
on the entire archive, even with fewer than 20 incoming files, and repeated on
every run, including dry runs. There was no progress message during indexing.

A read-only directory/stat scan of the configured external destination found
3,793 files totaling 33.01 GiB in 1.35 seconds. No archive contents were read in
that measurement. The old code would hash the entire eligible archive each run.
For illustration, reading 33 GiB at 100 MiB/s takes about 338 seconds before
accounting for hashing and filesystem overhead. That throughput is an example,
not a measured drive speed.

Metadata already uses a batched ExifTool invocation (up to 100 files). Failed
batch results can trigger single-file fallback. Each source is subsequently
read once for hashing and again for `shutil.copy2`. Large source videos can
therefore still take time even when the file count is small. The implementation
does not establish a USB, filesystem, or hardware fault.

## Implemented fix

Collect incoming byte sizes and hash destination files only when their sizes
match. Identical content necessarily has identical length, so this filtering
preserves SHA-256 duplicate detection across filenames and folders. No persistent
hash cache is introduced, so changed destination files are freshly checked.
Empty incoming sets skip destination traversal entirely. Directory traversal
prunes hidden directories, reports, and known filesystem metadata directories.

Add phase timings and messages before expensive startup work, plus source-hash
and individual-copy timings. These distinguish startup work from transfer time.

This still traverses archive directory entries. If this becomes the dominant
cost, a persistent incremental index is a possible next step, with explicit
invalidation for edited, removed, or replaced files. Equal-sized destination
files still require hashing; no universal speedup factor is claimed.

## Validation

All nine copy/duplicate tests pass. Regression coverage verifies size filtering,
duplicate detection with a different filename, directory pruning, and no
destination traversal for an empty size set. Existing collision tests pass.
The full suite ran 95 tests with six audit/display assertion failures; the
unchanged HEAD ran 91 tests with the exact same six failures.

No media was copied to or changed on the external drive during investigation.
Actual end-to-end transfer speed remains to be measured with an incoming batch;
the new timings make that measurement visible on the next copy run.
