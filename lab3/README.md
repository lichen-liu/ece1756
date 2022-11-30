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
