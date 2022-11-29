## To Run `ram_mapper`
```bash
# Default
python3 -m ram_mapper --lb=logic_block_count.txt --lr=logical_rams.txt --out=mapping.txt
```
```bash
# Configure arch
python3 -m ram_mapper --lb=logic_block_count.txt --lr=logical_rams.txt --out=mapping.txt --arch="-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1"
```
```bash
# Profile in serial mode
python3 -m cProfile -s cumtime -m ram_mapper --lb=logic_block_count.txt --lr=logical_rams.txt --out=mapping.txt -j1
```

## To Run `checker`
```bash
./checker_mac -t -d logical_rams.txt logic_block_count.txt mapping.txt
```
```bash
./checker_mac -l 1 1 -b 8192 32 10 1 -b 131072 128 300 1 -t logical_rams.txt logic_block_count.txt mapping.txt
```

## To UNITTEST
```bash
python3 -m unittest
```

## Count number of lines
```bash
find . -name "*.py" | xargs wc -l | sort -nr
```

## Notes
Combine RAMs to make wider RAM with no extra logic
• Combine RAMs to make deeper RAM with some extra logic – Which RAM to write enable (decode upper address bits)
– Which RAM drives the read output (mux read output)
• Logical RAMs with more ports than physical RAMs: expensive
– E.g. needed 2R and 1W but physical RAMs 1 R and 1W
Duplicate (double) implementation to make 2nd R port
– Any alternative?
• If physical RAM fast enough, can time-domain multiplex one physical port to make more logical ports

## Todo
