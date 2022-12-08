# ece1756

## Lab1
Report: [LATEX](https://www.overleaf.com/project/633a625e21adf003dcd788bb)

## Lab2
Report: [LATEX](https://www.overleaf.com/project/6360eb69ecda4de91a703475)
### ModelSim
Open ModelSim
```
modelsim18.start &
```
Simulate
```
cd <path to lab2.sv> # Navigate to the directory containing your design’s Verilog files
vlib work # Create a library called work in which your results will be placed
vlog lab2.sv # Compile lab1.sv
vlog lab2_tb.sv # Compile the testbench
vsim work.lab2_tb # Starts the simulator, with a top-level module of the lab1 testbench
view wave # Open the waveform window
run -all # Run simulation to completion which is OK because the testbench applies a fixed number of
     inputs and then issues a $stop command
```

## Lab3
Report: [LATEX](https://www.overleaf.com/project/638634f26e8285973ebd62c8)  
Refer to: [README](lab3/README.md)

## Lab4
Report: [LATEX](https://www.overleaf.com/project/6390e302b817e983f42dda72)
