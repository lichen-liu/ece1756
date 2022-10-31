// This module implements 2D covolution between a 3x3 filter and a 512-pixel-wide image of any height.
// It is assumed that the input image is padded with zeros such that the input and output images have
// the same size. The filter coefficients are symmetric in the x-direction (i.e. f[0][0] = f[0][2], 
// f[1][0] = f[1][2], f[2][0] = f[2][2] for any filter f) and their values are limited to integers
// (but can still be positive of negative). The input image is grayscale with 8-bit pixel values ranging
// from 0 (black) to 255 (white).
module lab2 (
	input  clk,			// Operating clock
	input  reset,			// Active-high reset signal (reset when set to 1)
	input  [71:0] i_f,		// Nine 8-bit signed convolution filter coefficients in row-major format (i.e. i_f[7:0] is f[0][0], i_f[15:8] is f[0][1], etc.)
	input  i_valid,			// Set to 1 if input pixel is valid
	input  i_ready,			// Set to 1 if consumer block is ready to receive a new pixel
	input  [7:0] i_x,		// Input pixel value (8-bit unsigned value between 0 and 255)
	output o_valid,			// Set to 1 if output pixel is valid
	output o_ready,			// Set to 1 if this block is ready to receive a new pixel
	output [7:0] o_y		// Output pixel value (8-bit unsigned value between 0 and 255)
);

localparam FILTER_SIZE = 3;	// Convolution filter dimension (i.e. 3x3)
localparam PIXEL_DATAW = 8;	// Bit width of image pixels and filter coefficients (i.e. 8 bits)

integer col, row, i; // variables to use in the for loop

// The following code is intended to show you an example of how to use paramaters and
// for loops in SytemVerilog. It also arrages the input filter coefficients for you
// into a nicely-arranged and easy-to-use 2D array of registers. However, you can ignore
// this code and not use it if you wish to.

logic signed [PIXEL_DATAW-1:0] r_f [FILTER_SIZE-1:0][FILTER_SIZE-1:0]; // 2D array of registers for filter coefficients
always_ff @ (posedge clk) begin
	// If reset signal is high, set all the filter coefficient registers to zeros
	// We're using a synchronous reset, which is recommended style for recent FPGA architectures
	if(reset)begin
		for(row = 0; row < FILTER_SIZE; row = row + 1) begin
			for(col = 0; col < FILTER_SIZE; col = col + 1) begin
				r_f[row][col] <= 0;
			end
		end
	// Otherwise, register the input filter coefficients into the 2D array signal
	end else begin
		for(row = 0; row < FILTER_SIZE; row = row + 1) begin
			for(col = 0; col < FILTER_SIZE; col = col + 1) begin
				// Rearrange the 72-bit input into a 3x3 array of 8-bit filter coefficients.
				// signal[a +: b] is equivalent to signal[a+b-1 : a]. You can try to plug in
				// values for col and row from 0 to 2, to understand how it operates.
				// For example at row=0 and col=0: r_f[0][0] = i_f[0+:8] = i_f[7:0]
				//	       at row=0 and col=1: r_f[0][1] = i_f[8+:8] = i_f[15:8]
				r_f[row][col] <= i_f[(row * FILTER_SIZE * PIXEL_DATAW)+(col * PIXEL_DATAW) +: PIXEL_DATAW];
			end
		end
	end
end

// Start of your code
logic enable;
assign enable = i_ready;

// **********************
// INGRESS
// **********************
// If pipelined, need to pipeline i_valid

// Logics for buffer of x
localparam IMAGE_WIDTH = 512;
localparam R_X_ROWS = FILTER_SIZE; // Always store 3 rows of i_x
localparam R_X_COL_WIDTH = IMAGE_WIDTH + 2;
localparam R_X_COL_ADDR_WIDTH = 10;


// Pixel RAM
// RAM input, need to be registered except for r_x_read_addr
logic [R_X_COL_ADDR_WIDTH-1:0] r_x_write_addr [R_X_ROWS-1:0]; // 0..511+2 (10 bit)
logic r_x_write_enable [R_X_ROWS-1:0];
logic unsigned [PIXEL_DATAW-1:0] r_x_write_data [R_X_ROWS-1:0];
// Registered inside module, read 3 words (3 x 8), lower addr: i.e., addr => read [addr+2: addr]. 0..511+2 (10 bit)
logic [R_X_COL_ADDR_WIDTH-1:0] r_x_read_addr [R_X_ROWS-1:0];
// RAM output
logic unsigned [FILTER_SIZE-1:0] [PIXEL_DATAW-1:0] r_x_read_data [R_X_ROWS-1:0]; // is registered inside module, 3 words (3 x 8)
pixelram pixel_ram 
(
	.clk(clk),
	.reset(reset),
	.enable(enable),
	// RAM input, unregistered inside module
	.i_write_addr(r_x_write_addr),
	.i_write_enable(r_x_write_enable),
	.i_write_data(r_x_write_data),
	.i_read_addr(r_x_read_addr), // read 3 words (3 x 8), lower addr: i.e., addr => read [addr+2: addr]
	// RAM output
	.o_read_data(r_x_read_data) // registered inside module, 3 words (3 x 8)
);


// Registers
// 0: [] [] [] [] [] [] [] []                         512 + 2
// 1: [] [] [] [] [] [] [] []                         512 + 2
// 2: [] [] [] [] [] [] [] []                         512 + 2
logic unsigned [1:0] r_x_row_logical_idx; // Count from 0 to R_X_ROWS - 1 (incl), logical order, not necessarily physical
logic unsigned [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx; // Count from 0 to R_X_COL_WIDTH (incl)
// Count from 0 to R_X_ROWS - 1 (incl), physical order
logic unsigned [R_X_ROWS-1:0][1:0] r_x_row_logical_to_physical_index;

// INGRESS: Stage -1
always_ff @ (posedge clk) begin
	if(reset) begin
		r_x_row_logical_idx <= 0;
		r_x_col_idx <= 0;
		
		for(i = 0; i < R_X_ROWS; i = i + 1) begin
			r_x_row_logical_to_physical_index[i] <= i;
		end

		for(row = 0; row < R_X_ROWS; row = row + 1) begin
			r_x_write_addr[row] <= 0;
			r_x_write_data[row] <= 0;
			r_x_write_enable[row] <= 0;
		end
	end else if (enable) begin
		// Do not write by default
		for(row = 0; row < R_X_ROWS; row = row + 1) begin
			r_x_write_addr[row] <= 0;
			r_x_write_data[row] <= 0;
			r_x_write_enable[row] <= 0;
		end
	 	if(i_valid) begin
			if(r_x_col_idx == R_X_COL_WIDTH) begin
				// Load input pixel to a new row at the current logical idx 0 (R_X_COL_WIDTH implies 0),
				// which would be discarded, then reused/overwritten as the new logical idx 2 in the next cycle
				r_x_write_addr[r_x_row_logical_to_physical_index[0]] <= 0;
				r_x_write_data[r_x_row_logical_to_physical_index[0]] <= i_x;
				r_x_write_enable[r_x_row_logical_to_physical_index[0]] <= 1;

				// Do the row shifting logic at the first input of the new row,
				// rather than at the last input of the old row (will have conflict
				// in writing old row and shifting old row)

				// Instead of shifting the actual data, shift the mapping from logical index to physical index
				// Shift the mapping, upward (idx[0]->idx[2])
				r_x_row_logical_to_physical_index <= {r_x_row_logical_to_physical_index[0], r_x_row_logical_to_physical_index[R_X_ROWS-1:1]};

				// Reset r_x_col_idx if necessary, continuing at idx 1.
				// Skipping idx 0 because we are at idx 0 currently
				r_x_col_idx <= 1;

				// Increment r_x_row_logical_idx_ipipelined only when r_x_row_logical_idx_ipipelined is 0 or 1,
				// so that r_x_row_logical_idx_ipipelined will reach to 2 in steady state
				if(r_x_row_logical_idx < R_X_ROWS - 1) begin
					r_x_row_logical_idx <= r_x_row_logical_idx + 1;
				end
			end else begin
				// Load data at logical idx 2
				r_x_write_addr[r_x_row_logical_to_physical_index[R_X_ROWS-1]] <= r_x_col_idx;
				r_x_write_data[r_x_row_logical_to_physical_index[R_X_ROWS-1]] <= i_x;
				r_x_write_enable[r_x_row_logical_to_physical_index[R_X_ROWS-1]] <= 1;

				// Increment r_x_col_idx
				r_x_col_idx <= r_x_col_idx + 1;
			end
		end
	end
end

// Pipeline registers for ingress
logic unsigned [1:0] r_x_row_logical_idx_ipipelined;
logic unsigned [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx_ipipelined;
logic unsigned [R_X_ROWS-1:0][1:0] r_x_row_logical_to_physical_index_ipipelined;
// INGRESS: Stage 0, to match registered RAM write
always_ff @ (posedge clk) begin
	if(reset) begin
		r_x_row_logical_idx_ipipelined <= 0;
		r_x_col_idx_ipipelined <= 0;
		r_x_row_logical_to_physical_index_ipipelined <= 0;
	end else if (enable) begin
		r_x_row_logical_idx_ipipelined <= r_x_row_logical_idx;
		r_x_col_idx_ipipelined <= r_x_col_idx;
		r_x_row_logical_to_physical_index_ipipelined <= r_x_row_logical_to_physical_index;
	end
end

// **********************
// EGRESS
// **********************

// Pipeline registers for egress
localparam NUM_EGRESS_STAGE = 1;
logic unsigned [NUM_EGRESS_STAGE-1:0] [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx_epipelined;
logic unsigned [NUM_EGRESS_STAGE-1:0] [1:0] r_x_row_logical_idx_epipelined;
logic unsigned [NUM_EGRESS_STAGE-1:0] [R_X_ROWS-1:0][1:0] r_x_row_logical_to_physical_index_epipelined;
always_ff @ (posedge clk) begin
	if(reset) begin
		r_x_col_idx_epipelined <= 0;
		r_x_row_logical_idx_epipelined <= 0;
		r_x_row_logical_to_physical_index_epipelined <= 0;
	end else if(enable) begin
		r_x_col_idx_epipelined <= /*{r_x_col_idx_epipelined[NUM_EGRESS_STAGE-2:0],*/ r_x_col_idx_ipipelined;
		r_x_row_logical_idx_epipelined <= /*{r_x_row_logical_idx_epipelined[NUM_EGRESS_STAGE-2:0],*/ r_x_row_logical_idx_ipipelined;
		r_x_row_logical_to_physical_index_epipelined <= r_x_row_logical_to_physical_index_ipipelined;
	end
end

// Logics for convolution core
// Registers
logic unsigned [PIXEL_DATAW-1:0] r_y;
logic r_y_valid;

// Computation

// Multiplication
logic unsigned [FILTER_SIZE-1:0] [PIXEL_DATAW-1:0] r_mult_i_pixel [R_X_ROWS-1:0];
// EGRESS: Stage -1
logic unsigned [R_X_COL_ADDR_WIDTH-1:0] adjusted_r_x_col_idx; // Count from 0 to R_X_COL_WIDTH (incl)
always_comb begin
	if (r_x_col_idx >= FILTER_SIZE) begin
		adjusted_r_x_col_idx = r_x_col_idx;
	end else begin
		adjusted_r_x_col_idx = FILTER_SIZE;
	end
end
logic signed [2*PIXEL_DATAW-1:0] products [FILTER_SIZE*FILTER_SIZE-1:0];
always_comb begin
		r_x_read_addr[0] = adjusted_r_x_col_idx - FILTER_SIZE;
		r_x_read_addr[1] = adjusted_r_x_col_idx - FILTER_SIZE;
		r_x_read_addr[2] = adjusted_r_x_col_idx - FILTER_SIZE;
		r_mult_i_pixel[0] = r_x_read_data[r_x_row_logical_to_physical_index_epipelined[0][0]];
		r_mult_i_pixel[1] = r_x_read_data[r_x_row_logical_to_physical_index_epipelined[0][1]];
		r_mult_i_pixel[2] = r_x_read_data[r_x_row_logical_to_physical_index_epipelined[0][2]];
end

genvar gen_i, gen_j;
generate
	for(gen_i = 0; gen_i < R_X_ROWS; gen_i = gen_i + 1) begin: mult_row
		for(gen_j = 0; gen_j < FILTER_SIZE; gen_j = gen_j + 1) begin: mult_col
			mult8x8 m (
				.i_filter(r_f[gen_i][FILTER_SIZE - (gen_j+1)]),
				.i_pixel(r_mult_i_pixel[gen_i][gen_j]),
				.o_res(products[gen_i * FILTER_SIZE + gen_j])
			);
		end
	end
endgenerate

// Reduction tree
logic signed [2*PIXEL_DATAW-1:0] sums [FILTER_SIZE*FILTER_SIZE-1-1:0];
add16p16 a01(
	.i_a(products[0]),
	.i_b(products[1]),
	.o_res(sums[0])
);
add16p16 a23(
	.i_a(products[2]),
	.i_b(products[3]),
	.o_res(sums[1])
);
add16p16 a45(
	.i_a(products[4]),
	.i_b(products[5]),
	.o_res(sums[2])
);
add16p16 a67(
	.i_a(products[6]),
	.i_b(products[7]),
	.o_res(sums[3])
);
add16p16 a0123(
	.i_a(sums[0]),
	.i_b(sums[1]),
	.o_res(sums[4])
);
add16p16 a4567(
	.i_a(sums[2]),
	.i_b(sums[3]),
	.o_res(sums[5])
);
add16p16 a01234567(
	.i_a(sums[4]),
	.i_b(sums[5]),
	.o_res(sums[6])
);
add16p16 a012345678(
	.i_a(sums[6]),
	.i_b(products[8]),
	.o_res(sums[7])
);
logic unsigned [PIXEL_DATAW-1:0] y;
always_comb begin
	if(sums[7]>255) begin
		y = 255;
	end else if (sums[7]<0) begin
		y = 0;
	end else begin
		y = sums[7][PIXEL_DATAW-1:0];
	end
end

// Output interface logics
// EGRESS: Stage 0
logic unsigned [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx_prev;
always_ff @ (posedge clk) begin
	if(reset) begin
		r_y <= 0;
		r_y_valid <= 0;
		r_x_col_idx_prev <= 0;
	end else if(enable) begin
		r_x_col_idx_prev <= r_x_col_idx_epipelined[NUM_EGRESS_STAGE-1];
		// By the time r_x_col_idx is 3, pixel at idx 2 is already written with i_x
		if(r_x_col_idx_prev != r_x_col_idx_epipelined[NUM_EGRESS_STAGE-1] &&
			r_x_col_idx_epipelined[NUM_EGRESS_STAGE-1] >= FILTER_SIZE &&
			r_x_row_logical_idx_epipelined[NUM_EGRESS_STAGE-1] == R_X_ROWS - 1) begin
			r_y <= y;
			r_y_valid <= 1;
		end else begin
			r_y <= 0;
			r_y_valid <= 0;
		end
	end
end

assign o_y = r_y;
// Ready for inputs as long as receiver is ready for outputs
assign o_ready = i_ready;
assign o_valid = r_y_valid & i_ready;

// End of your code

endmodule

/*******************************************************************************************/

// Multiplier module for 8x8 multiplications
module mult8x8 (
	input signed [7:0] i_filter,
	input unsigned [7:0] i_pixel,
	output signed [15:0] o_res
);

// Signed x unsigned gets unsigned, which is not what we intend.
// So convert unsigned to signed by treating unsigned number as positive (by adding a 0 to msb)
logic signed [8:0] i_pixel_signed;
assign i_pixel_signed = {1'b0, i_pixel};

assign o_res = i_filter * i_pixel_signed;

endmodule

/*******************************************************************************************/

// Adder module for 16+16 additions
module add16p16 (
	input signed [15:0] i_a,
	input signed [15:0] i_b,
	output signed [15:0] o_res
);

assign o_res = i_a + i_b;

endmodule


/*******************************************************************************************/

module pixelram #
(
	parameter FILTER_SIZE = 3,
	parameter PIXEL_DATAW = 8,
	parameter IMAGE_WIDTH = 512,
	parameter R_X_ROWS = FILTER_SIZE,
	parameter R_X_COL_WIDTH = IMAGE_WIDTH + 2,
	parameter R_X_COL_ADDR_WIDTH = 10
)
(
	input clk,
	input reset,
	input enable,
	// RAM input, unregistered inside the module except for i_read_addr
	input [R_X_COL_ADDR_WIDTH-1:0] i_write_addr [R_X_ROWS-1:0],
	input i_write_enable [R_X_ROWS-1:0],
	input unsigned [PIXEL_DATAW-1:0] i_write_data [R_X_ROWS-1:0],
	input [R_X_COL_ADDR_WIDTH-1:0] i_read_addr [R_X_ROWS-1:0], // registered inside the module, read 3 words (3 x 8), lower addr: i.e., addr => read [addr+2: addr]
	// RAM output
	output unsigned [FILTER_SIZE-1:0] [PIXEL_DATAW-1:0] o_read_data [R_X_ROWS-1:0] // registered, 3 words (3 x 8)
);
	// Wrap as RAM
	// 0: [] [] [] [] [] [] [] []                         512 + 2
	// 1: [] [] [] [] [] [] [] []                         512 + 2
	// 2: [] [] [] [] [] [] [] []                         512 + 2
	genvar gen_row;
	generate
		for(gen_row=0; gen_row<R_X_ROWS; gen_row=gen_row+1) begin: pixel_ram_row
			pixelrowram pixel_row_ram
			(
				.clk(clk),
				.reset(reset),
				.enable(enable),
				// RAM input, unregistered
				.i_write_addr(i_write_addr[gen_row]),
				.i_write_enable(i_write_enable[gen_row]),
				.i_write_data(i_write_data[gen_row]),
				.i_read_addr(i_read_addr[gen_row]), // read 3 words (3 x 8), lower addr: i.e., addr => read [addr+2: addr]
				// RAM output
				.o_read_data(o_read_data[gen_row]) // registered, 3 words (3 x 8)
			);
		end
	endgenerate
endmodule

/*******************************************************************************************/

module pixelrowram #
(
	parameter FILTER_SIZE = 3,
	parameter PIXEL_DATAW = 8,
	parameter IMAGE_WIDTH = 512,
	parameter R_X_COL_WIDTH = IMAGE_WIDTH + 2,
	parameter R_X_COL_ADDR_WIDTH = 10
)
(
	input clk,
	input reset,
	input enable,
	// RAM input, unregistered inside the module except for i_read_addr
	input [R_X_COL_ADDR_WIDTH-1:0] i_write_addr,
	input i_write_enable,
	input unsigned [PIXEL_DATAW-1:0] i_write_data,
	input [R_X_COL_ADDR_WIDTH-1:0] i_read_addr, // registered inside the module, read 3 words (3 x 8), lower addr: i.e., addr => read [addr+2: addr]
	// RAM output
	output logic unsigned [FILTER_SIZE-1:0] [PIXEL_DATAW-1:0] o_read_data // registered, 3 words (3 x 8)
);
	localparam NUM_R_X_ROW = FILTER_SIZE;
	
	// Wrap as RAM
	// 0: [] [] [] [] [] [] [] []                         512 + 2
	genvar gen_i;
	generate
		for (gen_i=0; gen_i<NUM_R_X_ROW; gen_i=gen_i+1) begin: pixel_ram_row_shard
			parameter bit [R_X_COL_ADDR_WIDTH-1:0] gen_i_trunc = gen_i;
			pixelrowramshard pixel_row_ram_shard
			(
				.clk(clk),
				.reset(reset),
				.enable(enable),
				// RAM input, unregistered
				.i_write_addr(i_write_addr),
				.i_write_enable(i_write_enable),
				.i_write_data(i_write_data),
				.i_read_addr(i_read_addr+gen_i_trunc), // read 1 word
				// RAM output
				.o_read_data(o_read_data[gen_i_trunc]) // registered, 1 word
			);
		end
	endgenerate
endmodule

/*******************************************************************************************/

module pixelrowramshard #
(
	parameter PIXEL_DATAW = 8,
	parameter IMAGE_WIDTH = 512,
	parameter R_X_COL_WIDTH = IMAGE_WIDTH + 2,
	parameter R_X_COL_ADDR_WIDTH = 10
)
(
	input clk,
	input reset,
	input enable,
	// RAM input, unregistered inside the module except for i_read_addr
	input [R_X_COL_ADDR_WIDTH-1:0] i_write_addr,
	input i_write_enable,
	input unsigned [PIXEL_DATAW-1:0] i_write_data,
	input [R_X_COL_ADDR_WIDTH-1:0] i_read_addr, // registered inside the module, read 1 word
	// RAM output
	output logic unsigned [PIXEL_DATAW-1:0] o_read_data // registered, 1 word
);
	// Wrap as RAM
	// 0: [] [] [] [] [] [] [] []                         512 + 2
	logic unsigned [PIXEL_DATAW-1:0] r_x_row_shard [R_X_COL_WIDTH-1:0]; // 2D array of registers for input pixels, row major
	logic [R_X_COL_ADDR_WIDTH-1:0] i_read_addr_reg;

	integer i;
	initial begin
		for (i=0; i<R_X_COL_WIDTH; i=i+1) begin
			r_x_row_shard[i] = 0;
		end
	end

	always_ff @ (posedge clk) begin
		if(reset) begin
			o_read_data <= 0;
			i_read_addr_reg <= 0;
		end else if(enable) begin
			i_read_addr_reg <= i_read_addr;
			o_read_data <= r_x_row_shard[i_read_addr_reg];
			if(i_write_enable) begin
				r_x_row_shard[i_write_addr] <= i_write_data;
			end
		end
	end
endmodule