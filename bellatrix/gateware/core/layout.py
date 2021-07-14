# layout for pipeline stages
_af_layout = [
    ('pc', 32, False)
]

_fd_layout = [
    ('pc',              32, True),
    ('instruction',     32, False),
    ('fetch_error',      1, False),
    ('prediction',       1, True),
    ('prediction_state', 2, True)
]

_dx_layout = [
    ('pc',              32, True),
    ('instruction',     32, True),
    ('gpr_rd',           5, True),
    ('gpr_we',           1, False),
    ('src_data1',       32, True),
    ('src_data2',       32, True),
    ('immediate',       32, True),
    ('funct3',           3, True),
    ('needed_in_m',      1, False),
    ('needed_in_w',      1, False),
    ('arithmetic',       1, True),
    ('logic',            1, True),
    ('compare',          1, True),
    ('shifter',          1, True),
    ('jump',             1, False),
    ('branch',           1, False),
    ('load',             1, False),
    ('store',            1, False),
    ('csr',              1, False),
    ('fence_i',          1, False),
    ('fence',            1, False),
    ('multiplier',       1, False),
    ('divider',          1, False),
    ('add_sub',          1, True),
    ('shift_dir',        1, True),
    ('shift_sign',       1, True),
    ('jb_base_addr',    32, True),
    ('ls_base_addr',    32, True),
    ('st_data',         32, True),
    ('csr_addr',        12, True),
    ('csr_we',           1, False),
    ('fetch_error',      1, False),
    ('ecall',            1, False),
    ('ebreak',           1, False),
    ('mret',             1, False),
    ('illegal',          1, False),
    ('prediction',       1, False),
    ('prediction_state', 2, True)
]

_xm_layout = [
    ('pc',                32, True),
    ('instruction',       32, True),
    ('gpr_rd',             5, True),
    ('gpr_we',             1, False),
    ('needed_in_w',        1, False),
    ('funct3',             3, True),
    ('compare',            1, False),
    ('shifter',            1, False),
    ('jump',               1, False),
    ('branch',             1, False),
    ('load',               1, False),
    ('store',              1, False),
    ('csr',                1, False),
    ('divider',            1, False),
    ('result',            32, True),
    ('ls_addr',           32, True),
    ('zero',               1, True),
    ('negative',           1, True),
    ('overflow',           1, True),
    ('carry',              1, True),
    ('jb_target',         32, True),
    ('csr_addr',          12, True),
    ('csr_we',             1, True),
    ('fetch_error',        1, False),
    ('ecall',              1, False),
    ('ebreak',             1, False),
    ('mret',               1, False),
    ('illegal',            1, False),
    ('ls_misalign',        1, False),
    ('prediction',         1, False),
    ('prediction_state',   2, True)

]

_mw_layout = [
    ('pc',         32, True),
    ('gpr_rd',      5, True),
    ('gpr_we',      1, False),
    ('result',     32, True),
    ('ld_result',  32, True),
    ('csr_result', 32, True),
    ('load',        1, True),
    ('csr',         1, True)
]
