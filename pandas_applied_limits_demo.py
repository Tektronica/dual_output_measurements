from dual_output_test import *


# GET BREAKPOINTS ----------------------------------------------------------------------------------------------
def breakpoints(params):
    bkpts = apply_user_limits(create_breakpoints('dualoutput_pts.csv'), params)
    try:
        bkpts.to_csv('breakpoints.csv', sep=',', index=False)  # write to csv
    except PermissionError:
        print('Breakpoints were not saved!\n'
              'The file, breakpoints.csv, may currently be open. Close before running.\n')


params = {'vmin': 0.013, 'vmax': 0.1,
          'imin': 3, 'imax': 3,
          'fmin': 65, 'fmax': 65,
          'pmin': 0, 'pmax': 0,
          'samples': 5}

breakpoints(params)
