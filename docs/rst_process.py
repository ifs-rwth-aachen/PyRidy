from pathlib import Path
import os

src_dir = Path("source/")
files= [os.path.join(src_dir, f) for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))]
files.remove('source\\conf.py')

for file in files:
    print("Processed RST file:", file)
    with open(file, "r") as f:
        lines = f.read()

    junk_strs = ["Submodules\n----------", "Subpackages\n-----------"]

    for junk in junk_strs:

        lines = lines.replace(junk, "")

    #lines = lines.replace(" module\n", "\n")
    lines = lines.replace(" package\n=", "\n")

    with open(file, "w") as f:
        f.write(lines)