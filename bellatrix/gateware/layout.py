# layout for pipeline stages
_af_layout = [
    ('pc', 32)
]

_fd_layout = [
    ('pc',              32),
    ('instruction',     32),
    ('instruction2',    32),
    ('fetch_error',      1),
    ('prediction',       1),
    ('prediction_state', 2)
]

_dx_layout = [
    ('pc',              32),
    ('instruction',     32),
    ('gpr_rd',           5),
    ('gpr_we',           1),
    ('src_data1',       32),
    ('src_data2',       32),
    ('src_data1b',      32),
    ('src_data2b',      32),
    ('immediate',       32),
    ('funct3',           3),
    ('needed_in_m',      1),
    ('needed_in_w',      1),
    ('arithmetic',       1),
    ('logic',            1),
    ('compare',          1),
    ('shifter',          1),
    ('jump',             1),
    ('branch',           1),
    ('load',             1),
    ('store',            1),
    ('csr',              1),
    ('fence_i',          1),
    ('fence',            1),
    ('multiplier',       1),
    ('divider',          1),
    ('add_sub',          1),
    ('shift_dir',        1),
    ('shift_sign',       1),
    ('jb_base_addr',    32),
    ('ls_base_addr',    32),
    ('st_data',         32),
    ('csr_addr',        12),
    ('csr_we',           1),
    ('fetch_error',      1),
    ('ecall',            1),
    ('ebreak',           1),
    ('mret',             1),
    ('illegal',          1),
    ('prediction',       1),
    ('prediction_state', 2)
]

_xm_layout = [
    ('pc',                32),
    ('instruction',       32),
    ('gpr_rd',             5),
    ('gpr_we',             1),
    ('needed_in_w',        1),
    ('funct3',             3),
    ('compare',            1),
    ('shifter',            1),
    ('jump',               1),
    ('branch',             1),
    ('load',               1),
    ('store',              1),
    ('csr',                1),
    ('divider',            1),
    ('result',            32),
    ('ls_addr',           32),
    ('zero',               1),
    ('zero2',              1),
    ('negative',           1),
    ('overflow',           1),
    ('carry',              1),
    ('jb_target',         32),
    ('csr_addr',          12),
    ('csr_we',             1),
    ('fetch_error',        1),
    ('ecall',              1),
    ('ebreak',             1),
    ('mret',               1),
    ('illegal',            1),
    ('ls_misalign',        1),
    ('prediction',         1),
    ('prediction_state',   2)

]

_mw_layout = [
    ('pc',         32),
    ('gpr_rd',      5),
    ('gpr_we',      1),
    ('result',     32),
    ('ld_result',  32),
    ('csr_result', 32),
    ('load',        1),
    ('csr',         1)
]
