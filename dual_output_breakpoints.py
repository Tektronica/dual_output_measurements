import pandas as pd
import itertools


def apply_user_limits(df, params):
    imin, imax = params['imin'], params['imax']
    vmin, vmax = params['vmin'], params['vmax']
    fmin, fmax = params['fmin'], params['fmax']
    pmin, pmax = params['pmin'], params['pmax']

    """
    The dataset iterated over keeps the following true for all rows: 
        1.	If voltage is less than VMAX and either the voltage is 0 while current is greater than IMIN or the voltage
            is greater than your VMIN
        2.	If current is less than IMAX and either the current is 0 while voltage is greater than VMIN or the current
            is greater than your IMIN
        3.	If frequency is within FMIN/FMAX
        4.	If phase is within PMIN/PMAX or voltage or current is 0
    """

    df_limited = df[(
            (
                    ((df['voltage'] == 0) & (df['current'] >= imin)) | (df['voltage'] >= vmin))
            & (
                    df['voltage'] <= vmax)
            & (
                    ((df['current'] == 0) & (df['voltage'] >= vmin)) | (df['current'] >= imin))
            & (
                    df['current'] <= imax)
            & (
                    df['frequency'] >= fmin) & (df['frequency'] <= fmax)
            & (
                    ((df['voltage'] == 0) | (df['current'] == 0)) | (df['phase'] >= pmin) & (df['phase'] <= pmax)
            ))].reset_index(drop=True)

    return df_limited


def apply_spec_limits(df):
    """
    POWER AND DUAL OUTPUT LIMIT SPECIFICATIONS
    =================================================================
    FREQUENCY       VOLTS               AMPS            AUXV
    =================================================================
    DC              0V TO +/- 1020V     0A TO 30.2A     0V TO 7V
    10Hz TO 65Hz    12mV to 1020V       1.2mA to 30.2A  10mV to 5V
    65Hz TO 500Hz   120mV to 1020V      12mA to 3.1A    100mV to 5V
    65Hz TO 1kHz    1.2V to 1020V       12mA to 30.2A   100mV to 5V
    1KHz TO 5kHz    1.2V to 500V        12mA to 3.1A    100mV to 5V
    5kHz TO 10kHz   1.2V to 250V        12mA to 1.2A    1V to 5V
    10kHZ TO 30kHz  1.2V to 250V        12mA to 1.2A    1V to 5V
    =================================================================
    """
    # drop even more unwanted breakpoint rows based on dual output limits
    # NOTE: NumPy arrays (of length greater than 1) and Pandas objects such as Series do not have a boolean value
    # In other words, they raise a ValueError when used as a boolean value. Hence "&" and "|" and not "and" and "or".
    df_limited = df[((df['frequency'] >= 10) & (df['frequency'] <= 65)
                     & (df['voltage'] >= 12e-3) & (df['voltage'] <= 1020)
                     & (df['current'] >= 1.2e-3) & (df['current'] <= 30.2)

                     | (df['frequency'] > 65) & (df['frequency'] <= 500)
                     & (df['voltage'] >= 120e-3) & (df['voltage'] <= 1020)
                     & (df['current'] >= 1.2e-3) & (df['current'] <= 30.2)

                     | (df['frequency'] > 65) & (df['frequency'] <= 1000)
                     & (df['voltage'] >= 1.2) & (df['voltage'] <= 1020)
                     & (df['current'] >= 12e-3) & (df['current'] <= 30.2)

                     | (df['frequency'] > 1000) & (df['frequency'] <= 5000)
                     & (df['voltage'] >= 1.2) & (df['voltage'] <= 500)
                     & (df['current'] >= 12e-3) & (df['current'] <= 3.1)

                     | (df['frequency'] > 5000) & (df['frequency'] <= 10000)
                     & (df['voltage'] >= 1.2) & (df['voltage'] <= 250)
                     & (df['current'] >= 12e-3) & (df['current'] <= 1.2)

                     | (df['frequency'] > 10000) & (df['frequency'] <= 30000)
                     & (df['voltage'] >= 1.2) & (df['voltage'] <= 250)
                     & (df['current'] >= 12e-3) & (df['current'] <= 1.2)
                     | (df['voltage'] == 0) | (df['current'] == 0) | (df['frequency'] == 0))].reset_index(drop=True)
    return df_limited


def create_breakpoints(file):
    """
    Builds a table of breakpoints by permutating through dual-output points read in.
    :param file: path to csv file containing dual-output points
    :return: returns the breakpoint data frame
    """
    # file where dual-output points are stored
    d = pd.read_csv(file)

    # create a list of the dual-output points (pnts) in the order we want to generate the table
    pnts = [d.voltage.dropna(), d.current.dropna(), d.frequency.dropna(), d.phase.dropna()]
    # create table of all permutations of the dual-output points
    df = pd.DataFrame(list(itertools.product(*pnts)), columns=['voltage', 'current', 'frequency', 'phase'])

    # drop unwanted breakpoint rows and then re-index the table
    df_filtered = df.drop(df[(((df['voltage'] == 0) | (df['current'] == 0)) & (df['phase'] > 0))
                             | ((df['voltage'] == 0) & (df['current'] == 0))
                             | ((df['frequency'] == 0) & (df['phase'] > 0))].index).reset_index(drop=True)

    df_filtered_limited = apply_spec_limits(df_filtered)

    # find the first index where the current column is no longer zero
    split = df_filtered_limited.voltage.ne(0).idxmax()
    # split the table at the index of first non zero
    top_df = df_filtered_limited.iloc[:split, :]
    btm_df = df_filtered_limited.iloc[split:, :]
    # sort the bottom half by the 'current' column
    btm_df_sorted = btm_df.sort_values(by=['current', 'voltage'], ascending=(True))

    # merge the tables back together using concatenation
    bkpts = pd.concat([top_df, btm_df_sorted], sort=False)

    return bkpts
