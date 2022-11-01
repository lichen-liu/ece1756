                            Throughput (GOPS)                                   Power (W)                       Energy Efficiency (GOPS/W)      Area Efficiency (GOPS/mm^2)
FPGA (20 nm)                4689.198GOPS                                        10.188W                         460.267GOPS/W                   4689.198GOPS / 400mm^2 = 11.723GOPS/mm^2
CPU (14 nm)                 64 * 512 * 512 * (9 + 8) / 4.85293ms = 58.771GOPS   65W                             0.904GOPS/W                     58.771GOPS / 276mm^2 = 0.213GOPS/mm^2
GPU (8 nm)                  64 * 512 * 512 * (9 + 8) / 0.506027ms = 563.631GOPS 220W                            2.562GOPS/W                     563.631GOPS / 393mm^2 = 1.434GOPS/mm^2
FPGA (scaled to 8 nm)       1.6 * 4689.198GOPS = 7502.717GOPS                   6.875W                          1091.304GOPS/W                  7502.717GOPS / (400mm^2 * 0.25) = 75.027GOPS/mm^2
CPU (scaled to 8 nm)        1.25 * 58.771GOPS = 73.464GOPS                      1.25 * 65W * 0.7 =  56.875W     1.292GOPS/W                     73.464GOPS / (276mm^2 * 0.5) = 0.532GOPS/mm^2


FPGA 8nm Power:
(
(0.08mW + 0.45mW + 0.20mW + 0.79mW) / 50MHz * 549.45 MHz * 1.6 * 506 +
2.82mW / 50MHz * 549.45 MHz * 1.6 +
1704.56mW + 0.19mW
) * 0.45
=6.875W