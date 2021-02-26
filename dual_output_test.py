from dmm_f8588A import *
from dmm_f5790B import *
from dut_f5560A import *
from dual_output_breakpoints import *

import time
import numpy as np
from pathlib import Path
import pandas as pd

# [PARAMETERS] #########################################################################################################
LOWS_TIED = True
COMPENSATION_USED = False


def get_measurement_length(df):
    # https://stackoverflow.com/a/15943975
    size = len(df.index)
    pos1 = df['voltage'].ne(0).idxmax()
    pos2 = df['current'].iloc[pos1:].ne(0).idxmax()
    return size - pos2


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
            f5560A_id = {'address': '129.196.136.130', 'port': '3490', 'gpib': '4', 'mode': 'GPIB'}
            f8588A_id = {'address': '10.205.92.241', 'port': '3490', 'gpib': '24', 'mode': 'GPIB'}
            f5790B_id = {'address': '', 'port': '', 'gpib': '6', 'mode': 'GPIB'}

            self.connect_to_f5560A(f5560A_id)
            self.connect_to_f8588A(f8588A_id)
            self.connect_to_f5790B(f5790B_id)

            if self.f5560A.healthy and self.f8588A.healthy and self.f5790B.healthy:
                self.connected = True
                try:
                    idn_dict = {'DUT': self.f5560A_IDN, 'DMM01': self.f8588A_IDN, 'DMM02': self.f5790B_IDN}
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
        self.close_f5790B()


class Test:
    def __init__(self, parent):
        self.frame = parent
        self.M = Instruments(self)

    def connect(self, instruments):
        self.M.close_instruments()
        time.sleep(2)
        try:
            self.M.connect(instruments)
        except ValueError as e:
            self.frame.error_dialog(e)

    def setup(self):
        # Fluke 5560A --------------------------------------------------------------------------------------------------
        self.M.setup_source()
        self.M.setup_f5790B(input_terminal='INPUT2', EXTRIG='OFF', HIRES='ON', EXTGUARD='ON')
        self.M.setup_f8588A(mode='CURR', function='AC')
        time.sleep(5)

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
        samples = params['samples']
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
                self.M.run_source(mode='V', rms=voltage, Ft=frequency)

                # measure voltage
                voltage_baseline_measurement[(voltage, frequency)] = self.M.read_voltage('INPUT2', samples=samples)[0]
                time.sleep(0.2)

                self.M.standby_f5560A()

            # single output current baseline measurement
            elif voltage == 0:
                print(f'single output (A): {current}A')
                self.M.run_source(mode='A', rms=current, Ft=frequency)
                self.M.set_f8588A_function(frequency)
                time.sleep(1)

                if COMPENSATION_USED:
                    self.set_compensation(current)

                # measure current
                current_baseline_measurement[(current, frequency)] = self.M.read_f8588A(samples=samples)[0]
                time.sleep(0.2)

                self.M.standby_f5560A()

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

                self.M.set_f8588A_function(frequency)
                time.sleep(1)

                self.f5560A.write(f'oper')
                # LOWS TIED/OPEN ---------------------------------------------------------------------------------------
                if LOWS_TIED:
                    self.M.lows('TIED')
                else:
                    self.M.lows('OPEN')

                if COMPENSATION_USED:
                    self.set_compensation(current)

                Vmeas, VOLT_STD = self.M.read_voltage('INPUT2', samples=samples)
                Imeas, CUR_STD = self.M.read_f8588A(samples=samples)[:1]
                time.sleep(1)

                self.M.standby_f5560A()

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
    
    def set_compensation(self, current):
        if current > 1:
            print('DIST_AMP - 47nF placed in distortion amplifier feedback.')
            self.M.f5560A.write('write P7P7, #hEC')  # turn COMP2 ON (distortion amp)
            self.M.f5560A.write('WAI')  # turn COMP2 ON (distortion amp)
            time.sleep(2)
        else:
            print('DIST_AMP - 2.2nF placed in distortion amplifier feedback.')
            self.M.f5560A.write('write P7P7, #hFC')  # turn COMP2 ON (distortion amp)
            self.M.f5560A.write('WAI')  # turn COMP2 ON (distortion amp)
            time.sleep(2)

    def close_instruments(self):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()
