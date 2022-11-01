Slow 900mV 100C Model 687.76 MHz 549.45 MHz clk limit due to minimum period restriction (tmin)

ALM Utilization: 213-47=166 / 427,200
2573x

DSP Utilization: 3 / 1,518
506x

BRAM (M20K) Utilization: 3 / 2,713
904x

Maximum Operating Frequency (MHz): Restricted 549.45 MHz (687.76 MHz)

Cycles for Test 7a (Hinton): 264222

Dynamic Power for one module @ maximum frequency (W):
DSP: 0.08mW
M20K: 0.45mW
Combinational cell: 0.20mW
Register cell: 0.79mW
// Toggle Rate: 8.518 millions of transitions / sec
(0.08mW + 0.45mW + 0.20mW + 0.79mW + 2.82mW) / 50MHz * 549.45 MHz = 47.69mW

Throughput of one module (GOPS)
#OP = 512 * 512 * (9 + 8) = 4456448
d_t = 264222 / 549.45M = 480.885us
9.267 GOPS

Throughput of full device (GOPS)
506 * 9.267 GOPS = 4689.102 GOPS

Total Power for full device (W)
Clock Network (dynamic): 2.82mW
Device Static: 1704.56mW
IO: 0.19mW

(0.08mW + 0.45mW + 0.20mW + 0.79mW) / 50MHz * 549.45 MHz * 506 +
2.82mW / 50MHz * 549.45 MHz +
1704.56mW + 0.19mW
10.188W
