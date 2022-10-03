module lab1 #
(
	parameter WIDTHIN = 16,		// Input format is Q2.14 (2 integer bits + 14 fractional bits = 16 bits)
	parameter WIDTHOUT = 32,	// Intermediate/Output format is Q7.25 (7 integer bits + 25 fractional bits = 32 bits)
	// Taylor coefficients for the first five terms in Q2.14 format
	parameter [WIDTHIN-1:0] A0 = 16'b01_00000000000000, // a0 = 1
	parameter [WIDTHIN-1:0] A1 = 16'b01_00000000000000, // a1 = 1
	parameter [WIDTHIN-1:0] A2 = 16'b00_10000000000000, // a2 = 1/2
	parameter [WIDTHIN-1:0] A3 = 16'b00_00101010101010, // a3 = 1/6
	parameter [WIDTHIN-1:0] A4 = 16'b00_00001010101010, // a4 = 1/24
	parameter [WIDTHIN-1:0] A5 = 16'b00_00000010001000  // a5 = 1/120
)
(
	input clk,
	input reset,	
	
	input i_valid,
	input i_ready,
	output o_valid,
	output o_ready,
	
	input [WIDTHIN-1:0] i_x,
	output [WIDTHOUT-1:0] o_y
);

logic enable;
assign enable = i_ready;

/*******************************************************************************************/
// Datapath
// Parameters
localparam [WIDTHOUT-1:0] A5_32b = 32'b0000000_0000001000100000000000000;  // a5 = 1/120

// Register
logic [WIDTHOUT-1:0] dp_tmp; // Register to hold intermediate result
logic [WIDTHIN-1:0] dp_x; // Register to hold input X

// Rigster control, (FSM output)
logic dp_tmp_enable;
logic dp_x_enable;

// Multiplexer control, (FSM output)
enum logic {FROM_A5_32B, FROM_DP_TMP} dp_mult_dataa_select;
enum logic [2:0] {FROM_A4, FROM_A3, FROM_A2, FROM_A1, FROM_A0} dp_addr_datab_select;
enum logic {FROM_MULT, FROM_ADDR} dp_tmp_d_select;

// Multiplexer output
logic [WIDTHOUT-1:0] dp_mult_dataa;
logic [WIDTHIN-1:0] dp_addr_datab;
logic [WIDTHOUT-1:0] dp_tmp_d;

// Mult and Addr output
logic [WIDTHOUT-1:0] dp_mult_out;
logic [WIDTHOUT-1:0] dp_addr_out;

// Mult and Addr
mult32x16 Mult0 (.i_dataa(dp_mult_dataa), 	.i_datab(dp_x), 	.o_res(dp_mult_out));
addr32p16 Addr0 (.i_dataa(dp_tmp), 	.i_datab(dp_addr_datab), 	.o_res(dp_addr_out));

// Multiplexer
always_comb begin
	case (dp_mult_dataa_select)
		FROM_DP_TMP: dp_mult_dataa = dp_tmp;
		FROM_A5_32B: dp_mult_dataa = A5_32b;
		default: dp_mult_dataa = 0;
	endcase

	case(dp_addr_datab_select)
		FROM_A4: dp_addr_datab = A4;
		FROM_A3: dp_addr_datab = A3;
		FROM_A2: dp_addr_datab = A2;
		FROM_A1: dp_addr_datab = A1;
		FROM_A0: dp_addr_datab = A0;
		default: dp_addr_datab = 0;
	endcase

	case(dp_tmp_d_select)
		FROM_MULT: dp_tmp_d = dp_mult_out;
		FROM_ADDR: dp_tmp_d = dp_addr_out;
		default: dp_tmp_d = 0;
	endcase
end

// Register
always_ff @(posedge clk or posedge reset) begin
	if (reset) begin
		dp_tmp <= 0;
		dp_x <= 0;
	end else if (enable) begin
		if (dp_tmp_enable) begin
			dp_tmp <= dp_tmp_d;
		end

		if (dp_x_enable) begin
			dp_x <= i_x;
		end
	end
end

assign o_y = dp_tmp;

/*******************************************************************************************/
// FSM

// FSM output
logic output_valid;
logic compute_busy;

// State
typedef enum logic [3:0] {RECEIVE_INPUT, COMPUTE_0, COMPUTE_1, COMPUTE_2, COMPUTE_3, COMPUTE_4, COMPUTE_5, COMPUTE_6, COMPUTE_7, COMPUTE_8, COMPUTE_9, SEND_OUTPUT} fsm_state_type;
fsm_state_type fsm_current_state; // Register
fsm_state_type fsm_next_state;

// State register
always_ff @(posedge clk or posedge reset) begin
	if (reset) begin
		fsm_current_state <= RECEIVE_INPUT;
	end else if (enable) begin
		fsm_current_state <= fsm_next_state;
	end
end

// State transition and control signal
always_comb begin
	case(fsm_current_state)
	RECEIVE_INPUT: begin
		if (i_valid) begin
			dp_tmp_enable = 0;
			dp_x_enable = 1;
			dp_mult_dataa_select = FROM_A5_32B;
			dp_addr_datab_select = FROM_A4;
			dp_tmp_d_select = FROM_MULT;
			output_valid = 0;
			compute_busy = 1;
			fsm_next_state = COMPUTE_0;
		end else begin
			dp_tmp_enable = 0;
			dp_x_enable = 0;
			dp_mult_dataa_select = FROM_A5_32B;
			dp_addr_datab_select = FROM_A4;
			dp_tmp_d_select = FROM_MULT;
			output_valid = 0;
			compute_busy = 0;
			fsm_next_state = RECEIVE_INPUT;
		end
	end
	COMPUTE_0: begin // tmp = A5_32b * x
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_A5_32B;
		dp_addr_datab_select = FROM_A4;
		dp_tmp_d_select = FROM_MULT;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_1;
	end
	COMPUTE_1: begin // tmp = tmp + A4
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A4;
		dp_tmp_d_select = FROM_ADDR;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_2;
	end
	COMPUTE_2: begin // tmp = tmp * x
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A3;
		dp_tmp_d_select = FROM_MULT;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_3;
	end
	COMPUTE_3: begin // tmp = tmp + A3
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A3;
		dp_tmp_d_select = FROM_ADDR;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_4;
	end
	COMPUTE_4: begin // tmp = tmp * x
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A2;
		dp_tmp_d_select = FROM_MULT;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_5;
	end
	COMPUTE_5: begin // tmp = tmp + A2
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A2;
		dp_tmp_d_select = FROM_ADDR;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_6;
	end
	COMPUTE_6: begin // tmp = tmp * x
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A1;
		dp_tmp_d_select = FROM_MULT;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_7;
	end
	COMPUTE_7: begin // tmp = tmp + A1
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A1;
		dp_tmp_d_select = FROM_ADDR;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_8;
	end
	COMPUTE_8: begin // tmp = tmp * x
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A0;
		dp_tmp_d_select = FROM_MULT;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = COMPUTE_9;
	end
	COMPUTE_9: begin // tmp = tmp + A0
		dp_tmp_enable = 1;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A0;
		dp_tmp_d_select = FROM_ADDR;
		output_valid = 0;
		compute_busy = 1;
		fsm_next_state = SEND_OUTPUT;
	end
	SEND_OUTPUT: begin
		dp_tmp_enable = 0;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_DP_TMP;
		dp_addr_datab_select = FROM_A0;
		dp_tmp_d_select = FROM_ADDR;
		output_valid = 1;
		compute_busy = 1;
		fsm_next_state = RECEIVE_INPUT;
	end
	default: begin
		dp_tmp_enable = 0;
		dp_x_enable = 0;
		dp_mult_dataa_select = FROM_A5_32B;
		dp_addr_datab_select = FROM_A4;
		dp_tmp_d_select = FROM_MULT;
		output_valid = 0;
		compute_busy = 0;
		fsm_next_state = RECEIVE_INPUT;
	end
	endcase
end

assign o_valid = output_valid & i_ready;
assign o_ready = ~compute_busy & i_ready;
endmodule

/*******************************************************************************************/

// Multiplier module for all the remaining 32x16 multiplications
module mult32x16 (
	input  [31:0] i_dataa,
	input  [15:0] i_datab,
	output [31:0] o_res
);

logic [47:0] result;

always_comb begin
	result = i_dataa * i_datab;
end

// The result of Q7.25 x Q2.14 is in the Q9.39 format. Therefore we need to change it
// to the Q7.25 format specified in the assignment by selecting the appropriate bits
// (i.e. dropping the most-significant 2 bits and least-significant 14 bits).
assign o_res = result[45:14];

endmodule

/*******************************************************************************************/

// Adder module for all the 32b+16b addition operations 
module addr32p16 (
	input [31:0] i_dataa,
	input [15:0] i_datab,
	output [31:0] o_res
);

// The 16-bit Q2.14 input needs to be aligned with the 32-bit Q7.25 input by zero padding
assign o_res = i_dataa + {5'b00000, i_datab, 11'b00000000000};

endmodule

/*******************************************************************************************/
