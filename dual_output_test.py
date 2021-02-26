from dmm_f8588A import *
from dut_f5790B import *
from dut_f5560A import *

import itertools
import time
import numpy as np
from pathlib import Path
import pandas as pd

import wx

# [PARAMETERS] #########################################################################################################
LOWS_TIED = True
COMPENSATION = False


def get_measurement_length(df):
    # https://stackoverflow.com/a/15943975
    size = len(df.index)
    pos1 = df['voltage'].ne(0).idxmax()
    pos2 = df['current'].iloc[pos1:].ne(0).idxmax()
    return size - pos2


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


########################################################################################################################
class Instruments(f5560A_instrument, f8588A_instrument, f5790B_instrument):
    def __init__(self, parent):
        f5560A_instrument.__init__(self)
        f8588A_instrument.__init__(self)
        self.analyzer = parent
        self.measurement = []
        self.connected = False

        self.M = Instruments(self)

    def connect(self, instruments):
        try:
            # ESTABLISH COMMUNICATION TO INSTRUMENTS -------------------------------------------------------------------
            f5560A_id = instruments['DUT']
            f8588A_id = instruments['DMM']
            self.connect_to_f5560A(f5560A_id)
            self.connect_to_f8588A(f8588A_id)

            if self.f5560A.healthy and self.f8588A.healthy:
                self.connected = True
                try:
                    idn_dict = {'DUT': self.f5560A_IDN, 'DMM': self.f8588A_IDN}
                    self.analyzer.frame.set_ident(idn_dict)
                    self.setup_source()
                except ValueError:
                    raise
            else:
                print('\nUnable to connect to all instruments.\n')
        except ValueError:
            raise ValueError('Could not connect. Timeout error occurred.')

    def close_instruments(self):
        time.sleep(1)
        self.close_f5560A()
        self.close_f8588A()


class Test:
    def __init__(self, parent):
        self.frame = parent

        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        f5560A_id = {'address': '129.196.136.130', 'port': '3490', 'gpib': '4', 'mode': 'GPIB'}
        f8588A_id = {'address': '10.205.92.241', 'port': '3490', 'gpib': '24', 'mode': 'GPIB'}
        f5790A_id = {'address': '', 'port': '', 'gpib': '6', 'mode': 'GPIB'}

        self.f5560A = VisaClient.VisaClient(f5560A_id)  # f5560A
        self.f8588A = VisaClient.VisaClient(f8588A_id)  # Current f8588A
        self.f5790A = VisaClient.VisaClient(f5790A_id)  # Voltage f5790A

        idn_dict = {'UUT': self.f5560A.query('*IDN?'),
                    'DMM01': self.f8588A.query('*IDN?'), 'DMM02': self.f5790A.query('*IDN?')}
        self.frame.set_ident(idn_dict)

    def setup(self):
        # Fluke 5560A --------------------------------------------------------------------------------------------------
        # f5560A.write('EXTGUARD ON')
        self.f5560A.write('wizard elbereth; ponwiz on')
        self.f5560A.write('MONITOR OFF')
        print(f"monitor: {self.f5560A.query('MONITOR?')}")
        self.f8588A.write('*RST')

        # Fluke 5790A --------------------------------------------------------------------------------------------------
        self.f5790A.write(f'*RST; INPUT INPUT2; EXTRIG OFF; HIRES ON; EXTGUARD ON')

        # Fluke 8588A --------------------------------------------------------------------------------------------------
        self.f8588A.write('*RST')
        time.sleep(10)

    def set_compensation(self, current):
        if current > 1:
            print('DIST_AMP - COMP 2 Set')
            self.f5560A.write('write P7P7, #hEC')  # turn COMP2 ON (distortion amp)
            self.f5560A.write('*WAI')
            time.sleep(2)
        else:
            print('DIST_AMP - COMP 3 Set')
            self.f5560A.write('write P7P7, #hFC')  # turn COMP3 ON (distortion amp)
            self.f5560A.write('*WAI')
            time.sleep(2)

    def run(self, params):
        Path('results').mkdir(parents=True, exist_ok=True)
        filename = 'test'
        path_to_file = f'results\\{filename}_{time.strftime("%Y%m%d_%H%M")}.csv'

        self.setup()  # setup_digitizer instruments

        # GET BREAKPOINTS ----------------------------------------------------------------------------------------------
        bkpts = apply_user_limits(create_breakpoints('dualoutput_pts.csv'), params)
        try:
            bkpts.to_csv('breakpoints.csv', sep=',', index=False)  # write to csv
        except PermissionError:
            print('Breakpoints were not saved!\n'
                  'The file, breakpoints.csv, may currently be open. Close before running.\n')

        # BUILD DICTIONARY ---------------------------------------------------------------------------------------------
        headers = ['voltage', 'current', 'frequency', 'phase',
                   'VREF', 'VMEAS', 'VDelta', 'VOLT_STD',
                   'IREF', 'IMEAS', 'IDelta', 'CUR_STD']
        self.frame.write_to_log(headers)

        # get length of datapoints excluding the baseline measurements to be performed
        N = get_measurement_length(bkpts)
        data = {item: np.zeros(N) for item in headers}

        current_baseline_measurement = {}
        voltage_baseline_measurement = {}
        state = 0
        old_state = 4
        spot = 0

        # RUN TEST -----------------------------------------------------------------------------------------------------
        # https://stackoverflow.com/a/11617194
        # https://towardsdatascience.com/how-to-make-your-pandas-loop-71-803-times-faster-805030df4f06
        for idx, row in bkpts.iterrows():
            voltage = row["voltage"]
            current = row["current"]
            frequency = row["frequency"]
            phase = row["phase"]

            # single output low current
            if current <= 3.1 and voltage == 0:
                state = 0
            # single output high current
            elif current > 3.1 and voltage == 0:
                state = 1
            # dual output low current
            elif current <= 3.1 and voltage != 0:
                state = 2
            # dual output high current
            elif current > 3.1 and voltage != 0:
                state = 3
            else:
                pass

            if state != old_state:
                self.prompt = True
                # https://stackoverflow.com/a/34427083
                self.frame.show_wiring_dialog(state)
                old_state = state
            else:
                pass

            # single output voltage baseline measurement
            if current == 0:
                print(f'single output (V): {voltage}V')
                self.f5560A.write(f'out {voltage}V, {frequency}Hz')
                time.sleep(1)
                self.f5560A.write('oper')
                time.sleep(2)

                # measure voltage
                voltage_baseline_measurement[(voltage, frequency)] = self.read_voltage(samples=params['samples'])[0]
                time.sleep(0.2)

                self.f5560A.write('STBY')
                time.sleep(1)
            # single output current baseline measurement
            elif voltage == 0:
                print(f'single output (A): {current}A')
                self.f5560A.write(f'out {current}A, {frequency}Hz')

                self.set_current_mode(frequency)
                time.sleep(1)

                self.f5560A.write('oper')
                time.sleep(2)

                if COMPENSATION:
                    self.set_compensation(current)

                # measure current
                current_baseline_measurement[(current, frequency)] = self.read_current(samples=params['samples'])[0]
                time.sleep(0.2)

                self.f5560A.write('STBY')
                time.sleep(1)
            # dual output measurement
            else:
                print(f'dual output: {voltage}V, {current}A, {frequency}Hz, {phase}')
                # 12mV range not working in dual output.
                # TODO: Still determining which registers to change. Here'amp_string a manual way...
                if 0 < voltage <= 12e-3:
                    self.f5560A.write(f'out {15e-3}V, {current}A,{frequency}Hz; phase {phase}')
                    time.sleep(1)
                    self.f5560A.write(f'out {voltage}V, {current}A,{frequency}Hz; phase {phase}')
                else:
                    self.f5560A.write(f'out {voltage}V, {current}A,{frequency}Hz; phase {phase}')

                self.set_current_mode(frequency)
                time.sleep(1)

                self.f5560A.write(f'oper')
                # LOWS TIED/OPEN ---------------------------------------------------------------------------------------
                if LOWS_TIED:
                    self.f5560A.write('lows tied')  # Lows tied
                    time.sleep(1)
                    # strobe relays
                    self.f5560A.write('mod p7p6,#h20,#h0')
                    time.sleep(1)
                    self.f5560A.write('mod p7p6,#h20,#h20')
                else:
                    self.f5560A.write('lows open')  # Lows tied
                    time.sleep(1)
                    # strobe relays
                    self.f5560A.write('mod p7p6,#h20,#h0')
                    time.sleep(1)
                    self.f5560A.write('mod p7p6,#h20,#h20')

                """                
                self.f5560A.write(f'mod ddsel0, #h10, #h00')  # bit 4 should be set low. Otherwise output current error.
                self.f5560A.write('*WAI')
                time.sleep(2)

                # LOWS TIED/OPEN ---------------------------------------------------------------------------------------
                if LOWS_TIED:
                    self.f5560A.write('mod A14RLY2,#h20,#h20')  # Lows tied
                    time.sleep(1)
                    self.f5560A.write('mod A6DDSEL0,#h3,#h02')  # Lows tied
                else:
                    self.f5560A.write('mod a14rly2,#h20,#h0')  # Lows open
                """

                if COMPENSATION:
                    self.set_compensation(current)

                Vmeas, VOLT_STD = self.read_voltage(samples=params['samples'])
                Imeas, CUR_STD = self.read_current(samples=params['samples'])
                time.sleep(1)

                self.f5560A.write('STBY')
                self.f5560A.write('*WAI')
                time.sleep(1)

                vref = voltage_baseline_measurement[(voltage, frequency)]
                iref = current_baseline_measurement[(current, frequency)]
                vdelta = (abs(Vmeas - vref) / vref) * 1e6
                idelta = (abs(Imeas - iref) / iref) * 1e6

                # save row of data to dictionary
                data['voltage'][spot] = float(self.f5560A.query('out?').split(',')[0])
                data['current'][spot] = float(self.f5560A.query('out?').split(',')[2])
                data['frequency'][spot] = frequency
                data['phase'][spot] = phase

                data['VREF'][spot] = vref
                data['VMEAS'][spot] = Vmeas
                data['VDelta'][spot] = vdelta

                data['IREF'][spot] = iref
                data['IMEAS'][spot] = Imeas
                data['IDelta'][spot] = idelta

                data['VOLT_STD'][spot] = VOLT_STD
                data['CUR_STD'][spot] = CUR_STD
                spot += 1
                new_row = [voltage, current, frequency, phase,
                           vref, Vmeas, vdelta, VOLT_STD,
                           iref, Imeas, idelta, CUR_STD]

                self.frame.write_to_log(new_row)
        self.f5560A.write('*RST')

        # convert dictionary to data frame
        df = pd.DataFrame(data)

        # write to csv
        df.to_csv(path_to_file, sep=',', index=False)
        # close instruments
        self.close_instruments()

        self.frame.flag_complete = True
        print('done')
        self.frame.toggle_ctrl()

    def set_current_mode(self, frequency):
        if frequency > 0:
            self.f8588A.write('CONF:CURR:AC')
            self.f8588A.write('CURR:AC:RANGE:AUTO ON')
        else:
            self.f8588A.write('CONF:CURR:DC')
            self.f8588A.write('CURR:DC:RANGE:AUTO ON')

        time.sleep(1)

    def read_current(self, samples=32):
        readings = np.zeros(samples)
        for idx in range(samples):
            self.f8588A.write('INIT:IMM')
            time.sleep(1)
            readings[idx] = self.f8588A.query('FETCH?')
            time.sleep(0.2)

        mean = readings.mean()
        std = np.sqrt(np.mean(abs(readings - mean) ** 2))
        return mean, std

    def read_voltage(self, samples=32):
        self.f5790A.write(f'INPUT INPUT2')
        self.f5790A.write('TRIG')
        time.sleep(1)

        readings = np.zeros(samples)
        for idx in range(samples):
            readings[idx] = self.f5790A.query('*WAI;VAL?').split(',')[0]
            time.sleep(0.2)

        mean = readings.mean()
        std = np.sqrt(np.mean(abs(readings - mean) ** 2))
        return mean, std

    def close_instruments(self):
        time.sleep(1)
        self.f5560A.close()
        self.f8588A.close()
        self.f5790A.close()
