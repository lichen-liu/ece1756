```
g++ -mavx -fopenmp conv_cpu.cpp utils.cpp -o conv_cpu

./run_cpu.sh 1 4 16 64
```
```
nvcc conv_gpu.cu utils.cpp -o conv_gpu
./conv_gpu hinton.pgm 16
./run_gpu.sh 1 4 16 64
```

GPU                                     0.0150802,  0.0400716,  0.137443,   0.506027

CPU (basic - no opt - 1 thread)         6.1022,     24.3058,    97.235,     389.021
CPU (vectorized - no opt - 1 thread)    3.19875,    13.0267,    51.8956,    207.304

CPU (basic - O2 - 1 thread)             1.2414,     4.97216,    19.8073,    79.2614
CPU (vectorized - O2 - 1 thread)        0.844073,   3.37512,    13.4929,    54.0134

CPU (basic - O3 - 1 thread)             0.533406,   2.12206,    8.46988,    33.8426
CPU (vectorized - O3 - 1 thread)        0.8823,     3.47462,    13.8976,    55.6889

CPU (basic - O3 - 4 threads)            0.576968,   0.61075,    1.2119,     4.85293
CPU (vectorized - O3 - 4 threads)       0.908206,   1.04593,    1.86823,    7.73344