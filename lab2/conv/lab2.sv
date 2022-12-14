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
// Registered inside module, read a pixel from 3 rows
logic [R_X_COL_ADDR_WIDTH-1:0] r_x_read_addr;
// RAM output
logic unsigned [PIXEL_DATAW-1:0] r_x_read_data [R_X_ROWS-1:0]; // is registered inside module, 3 rows of 1 pixel
pixelram pixel_ram 
(
	.clk(clk),
	.reset(reset),
	.enable(enable),
	// RAM input, unregistered inside module
	.i_write_addr(r_x_write_addr),
	.i_write_enable(r_x_write_enable),
	.i_write_data(r_x_write_data),
	.i_read_addr(r_x_read_addr),
	// RAM output
	.o_read_data(r_x_read_data)
);


// Registers
// 0: [] [] [] [] [] [] [] []                         512 + 2
// 1: [] [] [] [] [] [] [] []                         512 + 2
// 2: [] [] [] [] [] [] [] []                         512 + 2
logic unsigned [1:0] r_x_row_logical_idx; // Count from 0 to R_X_ROWS - 1 (incl), logical order, not necessarily physical
logic unsigned [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx; // Count from 0 to R_X_COL_WIDTH (incl)
logic unsigned [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx_read_addr_adjusted; // Count from 0 to R_X_COL_WIDTH (incl)
// Count from 0 to R_X_ROWS - 1 (incl), physical order
logic unsigned [R_X_ROWS-1:0][1:0] r_x_row_logical_to_physical_index;

// INGRESS: Stage -1
always_ff @ (posedge clk) begin
	if(reset) begin
		r_x_row_logical_idx <= 0;
		r_x_col_idx <= 0;
		r_x_col_idx_read_addr_adjusted <= 0;
		
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
		r_x_col_idx_read_addr_adjusted <= 0;
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
				r_x_col_idx_read_addr_adjusted <= 0;

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

				// Increment r_x_col_idx_read_addr_adjusted
				r_x_col_idx_read_addr_adjusted <= r_x_col_idx;
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
	if (enable) begin
		r_x_row_logical_idx_ipipelined <= r_x_row_logical_idx;
		r_x_col_idx_ipipelined <= r_x_col_idx;
		r_x_row_logical_to_physical_index_ipipelined <= r_x_row_logical_to_physical_index;
	end
end

// **********************
// EGRESS
// **********************

// Pipeline registers for egress
localparam NUM_EGRESS_STAGE = 9;
logic unsigned [NUM_EGRESS_STAGE-1:0] [R_X_COL_ADDR_WIDTH-1:0] r_x_col_idx_epipelined;
logic unsigned [NUM_EGRESS_STAGE-1:0] [1:0] r_x_row_logical_idx_epipelined;
logic unsigned [1:0] [R_X_ROWS-1:0][1:0] r_x_row_logical_to_physical_index_epipelined; // Not needed for full pipeline stage
always_ff @ (posedge clk) begin
	if(enable) begin
		r_x_col_idx_epipelined <= {r_x_col_idx_epipelined[NUM_EGRESS_STAGE-2:0], r_x_col_idx_ipipelined};
		r_x_row_logical_idx_epipelined <= {r_x_row_logical_idx_epipelined[NUM_EGRESS_STAGE-2:0], r_x_row_logical_idx_ipipelined};
		r_x_row_logical_to_physical_index_epipelined <= {r_x_row_logical_to_physical_index_epipelined[0:0], r_x_row_logical_to_physical_index_ipipelined};
	end
end

// Logics for convolution core
// Computation

// EGRESS: Stage -1
always_comb begin
	r_x_read_addr = r_x_col_idx_read_addr_adjusted;
end

// EGRESS: Stage 0, 1
// Signed x unsigned gets unsigned, which is not what we intend.
// So convert unsigned to signed by treating unsigned number as positive (by adding a 0 to msb)
logic signed [FILTER_SIZE-1:0] [PIXEL_DATAW:0] r_mult_i_pixel [R_X_ROWS-1:0];
logic [PIXEL_DATAW:0] r_x_read_data_reg [R_X_ROWS-1:0];
always_ff @ (posedge clk) begin
	if(enable) begin
		for(row=0; row<R_X_ROWS; row=row+1) begin
			r_x_read_data_reg[row] <= r_x_read_data[row];
			r_mult_i_pixel[row] <= {{1'b0, r_x_read_data_reg[r_x_row_logical_to_physical_index_epipelined[1][row]]}, r_mult_i_pixel[row][FILTER_SIZE-1:1]};
		end
	end
end

// Multiplication
// EGRESS: Stage 2, 3, 4, 5
logic signed [FILTER_SIZE-1:0] [2*PIXEL_DATAW-1:0] sums_stage_0;
genvar gen_row;
generate
	for(gen_row=0; gen_row<FILTER_SIZE; gen_row=gen_row+1) begin: mult
		mult8x8p8x8 m0(
			.clk(clk),
			.enable(enable),
			.i_filtera(r_f[gen_row][0]),
			.i_pixela0(r_mult_i_pixel[gen_row][0]),
			.i_pixela1(r_mult_i_pixel[gen_row][2]),
			.i_filterb(r_f[gen_row][1]),
			.i_pixelb(r_mult_i_pixel[gen_row][1]),
			.o_res(sums_stage_0[gen_row])
		);
	end
endgenerate

// Reduction tree
// EGRESS: Stage 6
logic signed [FILTER_SIZE-1:0] [2*PIXEL_DATAW-1:0] sums_stage_0_reg;
always_ff @ (posedge clk) begin
	if(enable) begin
		sums_stage_0_reg <= sums_stage_0;
	end
end

logic signed [2*PIXEL_DATAW-1:0] sums_stage_1 [1:0];
always_comb begin
	sums_stage_1[0] = sums_stage_0_reg[0] + sums_stage_0_reg[1];
	sums_stage_1[1] = sums_stage_0_reg[2];
end

logic signed [2*PIXEL_DATAW-1:0] sums_stage_2;
always_comb begin
	sums_stage_2 = sums_stage_1[0] + sums_stage_1[1];
end
// EGRESS: Stage 7
logic signed [2*PIXEL_DATAW-1:0] sums_stage_2_reg;
always_ff @ (posedge clk) begin
	if(enable)begin
		sums_stage_2_reg <= sums_stage_2;
	end
end

logic unsigned [PIXEL_DATAW-1:0] y;
always_comb begin
	if(sums_stage_2_reg>255) begin
		y = 255;
	end else if (sums_stage_2_reg<0) begin
		y = 0;
	end else begin
		y = sums_stage_2_reg[PIXEL_DATAW-1:0];
	end
end

// Output interface logics
// EGRESS: Stage 8
logic unsigned [PIXEL_DATAW-1:0] r_y;
logic r_y_valid;
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

// Multiplier module for 8x8 multiplications + 8x8 multiplications
module mult8x8p8x8 (
	input clk,
	input enable,
	input signed [7:0] i_filtera,
	input signed [8:0] i_pixela0,
	input signed [8:0] i_pixela1,
	input signed [7:0] i_filterb,
	input signed [8:0] i_pixelb,
	output logic signed [15:0] o_res
);

// Pipeline 0
logic signed [8:0] i_pixela0_reg, i_pixela1_reg, i_pixelb_reg;
logic signed [7:0] i_filtera_reg, i_filterb_reg;
always_ff @(posedge clk) begin
	if(enable)begin
		i_pixela0_reg <= i_pixela0;
		i_pixela1_reg <= i_pixela1;
		i_pixelb_reg <= i_pixelb;
		i_filtera_reg <= i_filtera;
		i_filterb_reg <= i_filterb;
	end
end

// Pipeline 1
logic signed [9:0] i_pixela01_reg_reg;
logic signed [8:0] i_pixelb_reg_reg;
logic signed [7:0] i_filtera_reg_reg, i_filterb_reg_reg;
always_ff @ (posedge clk) begin
	if(enable) begin
		i_pixela01_reg_reg <= i_pixela0_reg + i_pixela1_reg;
		i_pixelb_reg_reg <= i_pixelb_reg;
		i_filtera_reg_reg <= i_filtera_reg;
		i_filterb_reg_reg <= i_filterb_reg;
	end
end

// Pipeline 2
logic signed [9:0] i_pixela01_reg_reg_reg;
logic signed [8:0] i_pixelb_reg_reg_reg;
logic signed [7:0] i_filtera_reg_reg_reg, i_filterb_reg_reg_reg;
always_ff @ (posedge clk) begin
	if(enable) begin
		i_pixela01_reg_reg_reg <= i_pixela01_reg_reg;
		i_pixelb_reg_reg_reg <= i_pixelb_reg_reg;
		i_filtera_reg_reg_reg <= i_filtera_reg_reg;
		i_filterb_reg_reg_reg <= i_filterb_reg_reg;
	end
end

// Pipeline 3
always_ff @ (posedge clk) begin
	if(enable) begin
		o_res <= i_pixela01_reg_reg_reg * i_filtera_reg_reg_reg + i_pixelb_reg_reg_reg * i_filterb_reg_reg_reg;
	end
end
endmodule

/*******************************************************************************************/

module pixelram #
(
	parameter FILTER_SIZE = 3,
	parameter PIXEL_DATAW = 8,
	parameter IMAGE_WIDTH = 512,
	parameter R_X_ROWS = FILTER_SIZE,
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
	input [R_X_COL_ADDR_WIDTH-1:0] i_read_addr, // registered inside the module
	// RAM output
	output unsigned [PIXEL_DATAW-1:0] o_read_data [R_X_ROWS-1:0] // registered, 3 rows of 1 pixel
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
				.i_read_addr(i_read_addr), // read 1 pixel
				// RAM output
				.o_read_data(o_read_data[gen_row]) // registered, 1 pixel
			);
		end
	endgenerate
endmodule

/*******************************************************************************************/

module pixelrowram #
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
	input [R_X_COL_ADDR_WIDTH-1:0] i_read_addr, // registered inside the module
	// RAM output
	output logic unsigned [PIXEL_DATAW-1:0] o_read_data // registered
);
	// Wrap as RAM
	// 0: [] [] [] [] [] [] [] []                         512 + 2
	// 2D array of registers for input pixels, row major
	// set_global_assignment -name ADD_PASS_THROUGH_LOGIC_TO_INFERRED_RAMS OFF
	logic unsigned [PIXEL_DATAW-1:0] mem [R_X_COL_WIDTH-1:0];

	logic [R_X_COL_ADDR_WIDTH-1:0] i_read_addr_reg;

	integer i;
	initial begin
		for (i=0; i<R_X_COL_WIDTH; i=i+1) begin
			mem[i] = 0;
		end
	end

	always_ff @ (posedge clk) begin
		if(enable) begin
			i_read_addr_reg <= i_read_addr;
		end
	end

	always_ff @ (posedge clk) begin
		if(enable) begin
			if(i_write_enable) begin
				mem[i_write_addr] <= i_write_data;
			end
			o_read_data <= mem[i_read_addr_reg];
		end
	end
endmodule