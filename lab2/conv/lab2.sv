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

// Logics for buffer of x
localparam IMAGE_WIDTH = 512;
localparam R_X_ROWS = 3; // Always store 3 rows of i_x
localparam R_X_COL_WIDTH = IMAGE_WIDTH + 2;

// Registers
// 0: [] [] [] [] [] [] [] []                         512 + 2
// 1: [] [] [] [] [] [] [] []                         512 + 2
// 2: [] [] [] [] [] [] [] []                         512 + 2
logic unsigned [PIXEL_DATAW-1:0] r_x [R_X_ROWS-1:0][R_X_COL_WIDTH-1:0]; // 2D array of registers for input pixels
logic unsigned [1:0] r_x_row_logical_idx; // Count from 0 to R_X_ROWS - 1 (incl), logical order, not necessarily physical
logic unsigned [9:0] r_x_col_idx; // Count from 0 to R_X_COL_WIDTH (incl)
// Count from 0 to R_X_ROWS - 1 (incl), physical order
logic unsigned [R_X_ROWS-1:0][1:0] r_x_row_logical_to_physical_index;


	/// debug
	logic unsigned [31:0] i_x_counter;

always_ff @ (posedge clk) begin
	if(reset)begin
		for(row = 0; row < R_X_ROWS; row = row + 1) begin
			for(col = 0; col < R_X_COL_WIDTH; col = col + 1) begin
				r_x[row][col] <= 0;
			end
		end
		r_x_row_logical_idx <= 0;
		r_x_col_idx <= 0;
		
		for(i = 0; i < R_X_ROWS; i = i + 1) begin
			r_x_row_logical_to_physical_index[i] <= i;
		end

			/// debug
			i_x_counter <= 0;
	end else if(enable && i_valid) begin
		if(r_x_col_idx == R_X_COL_WIDTH) begin
			// Do the row shifting logic at the first input of the new row,
			// rather than at the last input of the old row (will have conflict
			// in writing old row and shifting old row)

			// Instead of shifting the actual data, shift the mapping from logical index to physical index
			// Shift the mapping, upward (idx[0]->idx[2])
			r_x_row_logical_to_physical_index <= {r_x_row_logical_to_physical_index[0], r_x_row_logical_to_physical_index[R_X_ROWS-1:1]};

			// Load input pixel to a new row at the current logical idx 0 (R_X_COL_WIDTH implies 0),
			// which would be discarded, then reused/overwritten as the new logical idx 2 in the next cycle
			r_x[r_x_row_logical_to_physical_index[0]][0] <= i_x;

			// Reset r_x_col_idx if necessary, continuing at idx 1.
			// Skipping idx 0 because we are at idx 0 currently
			r_x_col_idx <= 1;

			// Increment r_x_row_logical_idx only when r_x_row_logical_idx is 0 or 1,
			// so that r_x_row_logical_idx will reach to 2 in steady state
			if(r_x_row_logical_idx < R_X_ROWS - 1) begin
				r_x_row_logical_idx <= r_x_row_logical_idx + 1;
			end
		end else begin
			// Load data at logical idx 2
			r_x[r_x_row_logical_to_physical_index[R_X_ROWS-1]][r_x_col_idx] <= i_x;
			// Increment r_x_col_idx
			r_x_col_idx <= r_x_col_idx + 1;
		end
			/// debug
			i_x_counter <= i_x_counter + 1; 
	end
end

// Logics for convolution core
// Registers
logic unsigned [PIXEL_DATAW-1:0] r_y;
logic r_y_valid;

// Computation
logic unsigned [9:0] adjusted_r_x_col_idx; // Count from 0 to R_X_COL_WIDTH (incl)
always_comb begin
	if (r_x_col_idx >= FILTER_SIZE) begin
		adjusted_r_x_col_idx = r_x_col_idx;
	end else begin
		adjusted_r_x_col_idx = FILTER_SIZE;
	end
end
logic signed [2*PIXEL_DATAW-1:0] products [FILTER_SIZE*FILTER_SIZE-1:0];

// Multiplication
genvar gen_i, gen_j;
generate
	for(gen_i = 0; gen_i < R_X_ROWS; gen_i = gen_i + 1) begin: mult_row
		for(gen_j = 1; gen_j < FILTER_SIZE + 1; gen_j = gen_j + 1) begin: mult_col
				/// debug
				logic unsigned [9:0] mult_pixel_j;
				assign mult_pixel_j = adjusted_r_x_col_idx - gen_j;

			mult8x8 m (
				.i_filter(r_f[gen_i][FILTER_SIZE - gen_j]),
				.i_pixel(r_x[r_x_row_logical_to_physical_index[gen_i]][adjusted_r_x_col_idx - gen_j]),
				.o_res(products[gen_i * FILTER_SIZE + gen_j - 1])
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

// Output logics

	/// debug
	logic unsigned [31:0] o_y_counter;

always_ff @ (posedge clk) begin
	if(reset) begin
		r_y <= 0;
		r_y_valid <= 0;
			/// debug
			o_y_counter <= 0;
	end else if(enable) begin
		// By the time r_x_col_idx is 3, pixel at idx 2 is already written with i_x
		if(r_x_col_idx >= FILTER_SIZE && r_x_row_logical_idx == R_X_ROWS - 1) begin
			r_y <= y;
			r_y_valid <= 1;
				/// debug
				o_y_counter <= o_y_counter + 1;
		end else begin
			r_y <= 0;
			r_y_valid <= 0;
		end
	end
end

// Logics for output interface
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