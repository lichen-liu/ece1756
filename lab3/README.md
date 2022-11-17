## To Run
```bash
python3 -m ram_mapper
```

## To UNITTEST
```bash
python3 -m unittest
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