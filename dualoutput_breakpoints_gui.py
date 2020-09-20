import pandas as pd
import itertools
import VisaClient
import time
import numpy as np
from pathlib import Path
import wx
import wx.grid
from wx.adv import Animation, AnimationCtrl

import wx.propgrid as wxpg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
import os
import csv
import sys
import threading


def apply_user_limits(df, params):
    imin, imax = params['imin'], params['imax']
    vmin, vmax = params['vmin'], params['vmax']
    fmin, fmax = params['fmin'], params['fmax']
    pmin, pmax = params['pmin'], params['pmax']

    df_limited = df[((df['voltage'] == 0) & (df['current'] >= imin)
                     | (df['voltage'] >= vmin) & (df['voltage'] <= vmax)
                     & (df['current'] == 0) & (df['voltage'] >= vmin)
                     | (df['current'] >= imin) & (df['current'] <= imax)
                     & (df['frequency'] >= fmin) & (df['frequency'] <= fmax)
                     & (df['phase'] >= pmin) & (df['phase'] <= pmax))].reset_index(drop=True)

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


def get_measurement_length(df):
    # https://stackoverflow.com/a/15943975
    size = len(df.index)
    pos1 = df['voltage'].ne(0).idxmax()
    pos2 = df['current'].iloc[pos1:].ne(0).idxmax()
    return size - pos2


class Test:
    def __init__(self, parent):
        self.parent = parent
        self.prompt = True

        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        f5560A_id = {'ip_address': '129.196.136.130', 'port': '3490', 'gpib_address': '', 'mode': 'SOCKET'}
        f8588A_id = {'ip_address': '10.205.92.241', 'port': '3490', 'gpib_address': '', 'mode': 'SOCKET'}
        f5790A_id = {'ip_address': '', 'port': '', 'gpib_address': '6', 'mode': 'GPIB'}

        self.f5560A = VisaClient.VisaClient(f5560A_id)  # DUT
        self.f8588A = VisaClient.VisaClient(f8588A_id)  # Current DMM
        self.f5790A = VisaClient.VisaClient(f5790A_id)  # Voltage DMM

        idn_dict = {'UUT': self.f5560A.query('*IDN?'),
                    'DMM01': self.f8588A.query('*IDN?'), 'DMM02': self.f5790A.query('*IDN?')}
        self.parent.set_ident(idn_dict)

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
            self.f5560A.write('write P7P7, #hEC')  # turn COMP2 ON (distortion amp)
            self.f5560A.write('*WAI')
            time.sleep(2)
        else:
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
        bkpts.to_csv('breakpoints.csv', sep=',', index=False)  # write to csv

        # BUILD DICTIONARY ---------------------------------------------------------------------------------------------
        headers = ['voltage', 'current', 'frequency', 'phase',
                   'VREF', 'VMEAS', 'VDelta', 'VOLT_STD',
                   'IREF', 'IMEAS', 'IDelta', 'CUR_STD']
        self.parent.write_to_log(headers)

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
                wx.CallAfter(self.parent.open_dialog, state)
                while self.prompt:
                    pass
                old_state = state
            else:
                pass

            # single output voltage baseline measurement
            if current == 0:
                print(f'single output: {voltage}V')
                self.f5560A.write(f'out {voltage}V, {frequency}Hz')
                time.sleep(1)
                self.f5560A.write('oper')
                time.sleep(2)

                voltage_baseline_measurement[(voltage, frequency)] = self.read_voltage()[0]  # measure voltage
                time.sleep(0.2)
                self.f5560A.write('STBY')
                time.sleep(1)
            # single output current baseline measurement
            elif voltage == 0:
                print(f'single output: {current}A')
                self.f5560A.write(f'out {current}A, {frequency}Hz')
                time.sleep(1)
                self.f5560A.write('oper')
                time.sleep(2)
                self.set_compensation(current)

                current_baseline_measurement[(current, frequency)] = self.read_current()[0]  # measure current
                time.sleep(0.2)
                self.f5560A.write('STBY')
                time.sleep(1)
            # dual output measurement
            else:
                # 12mV range not working in dual output.
                # TODO: Still determining which registers to change. Here's a manual way...
                if 0 < voltage <= 12e-3:
                    self.f5560A.write(f'out {15e-3}V, {current}A,{frequency}Hz; phase {phase}')
                    time.sleep(1)
                    self.f5560A.write(f'out {voltage}V, {current}A,{frequency}Hz; phase {phase}')
                else:
                    self.f5560A.write(f'out {voltage}V, {current}A,{frequency}Hz; phase {phase}')

                time.sleep(1)
                self.f5560A.write(f'oper')
                self.f5560A.write(f'mod ddsel0, #h10, #h00')  # bit 4 should be set low. Otherwise output current error.
                self.f5560A.write('*WAI')
                time.sleep(2)

                # LOWS TIED/OPEN ---------------------------------------------------------------------------------------
                self.f5560A.write('mod a14rly2,#h20,#h20')  # Lows tied
                # f5560A.write('mod a14rly2,#h20,#h0')  # Lows open
                print(f"lows? {self.f5560A.query('lows?')}\n")
                time.sleep(1)

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

                self.parent.write_to_log([voltage, current, frequency, phase,
                                          vref, Vmeas, vdelta, VOLT_STD,
                                          iref, Imeas, idelta, CUR_STD])
        self.f5560A.write('*RST')

        # convert dictionary to data frame
        df = pd.DataFrame(data)
        df.to_csv(path_to_file, sep=',', index=False)  # write to csv
        self.close_instruments()

    def read_current(self, samples=32):
        self.f8588A.write('CONF:CURR:AC')
        self.f8588A.write('CURR:AC:RANGE:AUTO ON')
        time.sleep(1)

        readings = np.zeros(samples)
        for idx in range(samples):
            self.f8588A.write('INIT:IMM')
            readings[idx] = self.f8588A.query('FETCH?;*WAI')
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


class TestFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1384, 584))

        self.T = Test
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.daemon = True

        self.row = 0
        self.prevLine = ''
        self.line = ''
        self.table = {}
        self.overlay = {}
        self.ax = None
        self.x, self.y = [0.], [[0.]]
        self.flag_complete = False

        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.panel_2 = wx.Panel(self.panel_1, wx.ID_ANY)
        self.text_ctrl_9 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_10 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_11 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_1 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_2 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "1020")
        self.text_ctrl_3 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_4 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "29")
        self.text_ctrl_5 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_6 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "30000")
        self.text_ctrl_7 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_8 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "270")
        self.text_ctrl_12 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "15")

        self.btn_run = wx.Button(self.panel_2, wx.ID_ANY, "RUN")
        self.btn_defaults = wx.Button(self.panel_2, wx.ID_ANY, "Defaults")
        self.grid_1 = MyGrid(self.panel_2)

        # Run Measurement (start subprocess)
        on_run_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_run_event, self.btn_run)
        # Pressing enter sends command to test
        on_set_defaults = lambda event: self.set_defaults(event)
        self.Bind(wx.EVT_BUTTON, on_set_defaults, self.btn_defaults)

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("Dual Output")
        self.text_ctrl_9.SetMinSize((200, 23))
        self.text_ctrl_10.SetMinSize((200, 23))
        self.text_ctrl_11.SetMinSize((200, 23))
        self.text_ctrl_1.SetMinSize((50, 23))
        self.text_ctrl_2.SetMinSize((50, 23))
        self.text_ctrl_3.SetMinSize((50, 23))
        self.text_ctrl_4.SetMinSize((50, 23))
        self.text_ctrl_5.SetMinSize((50, 23))
        self.text_ctrl_6.SetMinSize((50, 23))
        self.text_ctrl_7.SetMinSize((50, 23))
        self.text_ctrl_8.SetMinSize((50, 23))
        self.text_ctrl_12.SetMinSize((50, 23))
        self.grid_1.CreateGrid(30, 12)
        # end wxGlade

    def __do_layout(self):
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_1 = wx.GridBagSizer(0, 0)
        label_1 = wx.StaticText(self.panel_2, wx.ID_ANY, "DUAL OUTPUT")
        label_1.SetFont(wx.Font(15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_1, (0, 0), (1, 4), 0, 0)
        grid_sizer_1.Add(self.grid_1, (0, 4), (14, 1), wx.EXPAND | wx.LEFT, 5)
        label_14 = wx.StaticText(self.panel_2, wx.ID_ANY, "UUT", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_14.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_14, (1, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        grid_sizer_1.Add(self.text_ctrl_9, (1, 1), (1, 3), wx.ALL, 5)
        label_15 = wx.StaticText(self.panel_2, wx.ID_ANY, "DMM (Current)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_15.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_15, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        grid_sizer_1.Add(self.text_ctrl_10, (2, 1), (1, 3), wx.ALL, 5)
        label_16 = wx.StaticText(self.panel_2, wx.ID_ANY, "DMM (Voltage)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_16.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_16, (3, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        grid_sizer_1.Add(self.text_ctrl_11, (3, 1), (1, 3), wx.ALL, 5)
        static_line_1 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_1.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_1, (4, 0), (1, 4), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.TOP, 5)
        label_12 = wx.StaticText(self.panel_2, wx.ID_ANY, "FEATURE", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_12.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_12, (5, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        label_10 = wx.StaticText(self.panel_2, wx.ID_ANY, "MIN", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_10.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_10, (5, 1), (1, 1), wx.ALIGN_CENTER | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_11 = wx.StaticText(self.panel_2, wx.ID_ANY, "MAX", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_11.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_11, (5, 2), (1, 1), wx.ALIGN_CENTER | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_13 = wx.StaticText(self.panel_2, wx.ID_ANY, "UNIT", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_13.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_13, (5, 3), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_2 = wx.StaticText(self.panel_2, wx.ID_ANY, "Voltage: ", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_2.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_2, (6, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        grid_sizer_1.Add(self.text_ctrl_1, (6, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_1.Add(self.text_ctrl_2, (6, 2), (1, 1), wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_3 = wx.StaticText(self.panel_2, wx.ID_ANY, "(V)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_3.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_3, (6, 3), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_4 = wx.StaticText(self.panel_2, wx.ID_ANY, "Current:", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_4.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_4, (7, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        grid_sizer_1.Add(self.text_ctrl_3, (7, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_1.Add(self.text_ctrl_4, (7, 2), (1, 1), wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_7 = wx.StaticText(self.panel_2, wx.ID_ANY, "(A)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_7.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_7, (7, 3), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_5 = wx.StaticText(self.panel_2, wx.ID_ANY, "Frequency:", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_5.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_5, (8, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        grid_sizer_1.Add(self.text_ctrl_5, (8, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_1.Add(self.text_ctrl_6, (8, 2), (1, 1), wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_8 = wx.StaticText(self.panel_2, wx.ID_ANY, "(Hz)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_8.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_8, (8, 3), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_6 = wx.StaticText(self.panel_2, wx.ID_ANY, "Phase:", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_6.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_6, (9, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        grid_sizer_1.Add(self.text_ctrl_7, (9, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_1.Add(self.text_ctrl_8, (9, 2), (1, 1), wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        label_9 = wx.StaticText(self.panel_2, wx.ID_ANY, "(deg)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_9.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_9, (9, 3), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        static_line_2 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_2.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_2, (10, 0), (1, 4), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.TOP, 5)
        label_17 = wx.StaticText(self.panel_2, wx.ID_ANY, "Samples (N):", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_17.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_17, (11, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        grid_sizer_1.Add(self.text_ctrl_12, (11, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_18 = wx.StaticText(self.panel_2, wx.ID_ANY, "(#)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_18.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_18, (11, 2), (1, 2), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        static_line_3 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_3.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_3, (12, 0), (1, 4), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.TOP, 5)
        grid_sizer_1.Add(self.btn_run, (13, 0), (1, 2), 0, 0)
        grid_sizer_1.Add(self.btn_defaults, (13, 2), (1, 2), wx.ALIGN_RIGHT, 0)
        self.panel_2.SetSizer(grid_sizer_1)
        sizer_2.Add(self.panel_2, 1, wx.ALL | wx.EXPAND, 10)
        self.panel_1.SetSizer(sizer_2)
        sizer_1.Add(self.panel_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        self.Layout()

    def on_run(self, evt):
        self.lock_text_ctrl()
        self.thread.start()

    def run(self):
        print('run_single!')
        self.flag_complete = False
        self.T = Test(self)
        self.T.run(self.get_values())
        self.flag_complete = True

    def lock_text_ctrl(self):
        self.text_ctrl_1.Enable(False)
        self.text_ctrl_2.Enable(False)
        self.text_ctrl_3.Enable(False)
        self.text_ctrl_4.Enable(False)
        self.text_ctrl_5.Enable(False)
        self.text_ctrl_6.Enable(False)
        self.text_ctrl_7.Enable(False)
        self.text_ctrl_8.Enable(False)
        self.text_ctrl_12.Enable(False)

    def set_defaults(self, evt):
        self.text_ctrl_1.SetValue("0")
        self.text_ctrl_2.SetValue("1020")
        self.text_ctrl_3.SetValue("0")
        self.text_ctrl_4.SetValue("29")
        self.text_ctrl_5.SetValue("0")
        self.text_ctrl_6.SetValue("30000")
        self.text_ctrl_7.SetValue("0")
        self.text_ctrl_8.SetValue("270")
        self.text_ctrl_12.SetValue("15")

    def get_values(self):
        return {'vmin': float(self.text_ctrl_1.GetValue()), 'vmax': float(self.text_ctrl_2.GetValue()),
                'imin': float(self.text_ctrl_3.GetValue()), 'imax': float(self.text_ctrl_4.GetValue()),
                'fmin': float(self.text_ctrl_5.GetValue()), 'fmax': float(self.text_ctrl_6.GetValue()),
                'pmin': float(self.text_ctrl_7.GetValue()), 'pmax': float(self.text_ctrl_8.GetValue()),
                'samples': int(self.text_ctrl_12.GetValue())}

    def set_ident(self, idn_dict):
        self.text_ctrl_9.SetValue(idn_dict['UUT'])  # UUT
        self.text_ctrl_10.SetValue(idn_dict['DMM01'])  # current DMM
        self.text_ctrl_11.SetValue(idn_dict['DMM02'])  # voltage DMM

    def open_dialog(self, config):
        dlg = TestDialog(self, config, None, wx.ID_ANY, "")
        dlg.ShowModal()
        dlg.Destroy()
        self.T.prompt = False

    def write_header(self, header):
        if not self.table:
            self.table = {key: [] for key in header}
        else:
            self.table = {header[col]: self.table[key] for col, key in enumerate(self.table.keys())}

        self.grid_1.write_list_to_row(self.row, self.table.keys())
        self.row += 1

    def write_to_log(self, row_data):
        self.grid_1.write_list_to_row(self.row, row_data)
        self.row += 1

        if not self.table:
            self.table = {f'col {idx}': [item] for idx, item in enumerate(row_data)}
        else:
            for idx, key in enumerate(self.table.keys()):
                self.table[key].append(row_data[idx])


class TestDialog(wx.Dialog):
    def __init__(self, parent, pos, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_DIALOG_STYLE
        super(TestDialog, self).__init__(parent, title='Change connection:')
        self.pos = pos
        self.panel_5 = wx.Panel(self, wx.ID_ANY)
        self.btn_continue = wx.Button(self.panel_5, wx.ID_ANY, "CONTINUE")
        self.btn_continue.Bind(wx.EVT_BUTTON, self.onContinue)

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("dialog")
        self.btn_continue.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))

    def __do_layout(self):
        sizer_5 = wx.BoxSizer(wx.VERTICAL)
        sizer_6 = wx.BoxSizer(wx.VERTICAL)
        label_19 = wx.StaticText(self.panel_5, wx.ID_ANY, "Change Connections...")
        label_19.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        sizer_6.Add(label_19, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        if False:
            # TODO: Get gifs working!!
            # https://stackoverflow.com/a/49403198
            # https://github.com/wxWidgets/Phoenix/blob/master/demo/AnimationCtrl.py
            gif = AnimationCtrl(self.panel_5, wx.ID_ANY, size=(456, 448))
            gif.LoadFile(f'images\\gifs\\connection0{self.pos + 1}.gif', animType=wx.adv.ANIMATION_TYPE_ANY)
            gif.SetBackgroundColour(self.GetBackgroundColour())
            gif.Play()
            sizer_6.Add(gif, 1)
        # For now, use a static image...
        else:
            bitmap_1 = wx.StaticBitmap(self.panel_5, wx.ID_ANY,
                                       wx.Bitmap(f'images\\connection0{self.pos + 1}.jpg', wx.BITMAP_TYPE_ANY))
            sizer_6.Add(bitmap_1, 0, 0, 0)

        sizer_6.Add(self.btn_continue, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        self.panel_5.SetSizer(sizer_6)
        sizer_5.Add(self.panel_5, 1, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(sizer_5)
        sizer_5.Fit(self)
        self.Layout()

    def onContinue(self, evt):
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            evt.Skip()
        else:
            self.Close()


class MyGrid(wx.grid.Grid):
    def __init__(self, parent):
        """Constructor"""
        wx.grid.Grid.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0)
        self.selected_rows = []
        self.selected_cols = []
        self.history = []

        self.frame_number = 1

        # test all the events
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnCellLeftClick)
        self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnCellRightClick)
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.OnCellLeftDClick)
        self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_DCLICK, self.OnCellRightDClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnLabelLeftClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnLabelRightClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.OnLabelLeftDClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_DCLICK, self.OnLabelRightDClick)
        self.Bind(wx.grid.EVT_GRID_ROW_SIZE, self.OnRowSize)
        self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnColSize)
        self.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.OnRangeSelect)
        self.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.OnCellChange)
        self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnSelectCell)
        self.Bind(wx.grid.EVT_GRID_EDITOR_SHOWN, self.OnEditorShown)
        self.Bind(wx.grid.EVT_GRID_EDITOR_HIDDEN, self.OnEditorHidden)
        self.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, self.OnEditorCreated)

    def OnCellLeftClick(self, event):
        print("OnCellLeftClick: (%d,%d) %s\n" % (event.GetRow(), event.GetCol(), event.GetPosition()))
        event.Skip()

    def OnCellRightClick(self, event):
        print("OnCellRightClick: (%d,%d) %s\n" % (event.GetRow(), event.GetCol(), event.GetPosition()))
        menu_contents = [(wx.NewId(), "Cut", self.onCut),
                         (wx.NewId(), "Copy", self.onCopy),
                         (wx.NewId(), "Paste", self.onPaste)]
        popup_menu = wx.Menu()
        for menu_item in menu_contents:
            if menu_item is None:
                popup_menu.AppendSeparator()
                continue
            popup_menu.Append(menu_item[0], menu_item[1])
            self.Bind(wx.EVT_MENU, menu_item[2], id=menu_item[0])

        self.PopupMenu(popup_menu, event.GetPosition())
        popup_menu.Destroy()
        return

    def OnCellLeftDClick(self, evt):
        print("OnCellLeftDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnCellRightDClick(self, evt):
        print("OnCellRightDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelLeftClick(self, evt):
        print("OnLabelLeftClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelRightClick(self, evt):
        print("OnLabelRightClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelLeftDClick(self, evt):
        print("OnLabelLeftDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelRightDClick(self, evt):
        print("OnLabelRightDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnRowSize(self, evt):
        print("OnRowSize: row %d, %s\n" % (evt.GetRowOrCol(), evt.GetPosition()))
        evt.Skip()

    def OnColSize(self, evt):
        print("OnColSize: col %d, %s\n" % (evt.GetRowOrCol(), evt.GetPosition()))
        evt.Skip()

    def OnRangeSelect(self, evt):
        if evt.Selecting():
            msg = 'Selected'
        else:
            msg = 'Deselected'
        print("OnRangeSelect: %s  top-left %s, bottom-right %s\n" % (
            msg, evt.GetTopLeftCoords(), evt.GetBottomRightCoords()))
        evt.Skip()

    def OnCellChange(self, evt):
        print("OnCellChange: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        # Show how to stay in a cell that has bad data.  We can'thread_continuous just
        # call SetGridCursor here since we are nested inside one so it
        # won'thread_continuous have any effect.  Instead, set coordinates to move to in
        # idle time.
        value = self.GetCellValue(evt.GetRow(), evt.GetCol())
        if value == 'no good':
            self.moveTo = evt.GetRow(), evt.GetCol()

    def OnSelectCell(self, evt):
        if evt.Selecting():
            msg = 'Selected'
        else:
            msg = 'Deselected'
        print("OnSelectCell: %s (%d,%d) %s\n" % (msg, evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        # Another way to stay in a cell that has a bad value...
        row = self.GetGridCursorRow()
        col = self.GetGridCursorCol()
        if self.IsCellEditControlEnabled():
            self.HideCellEditControl()
            self.DisableCellEditControl()
        value = self.GetCellValue(row, col)
        if value == 'no good 2':
            return  # cancels the cell selection
        evt.Skip()

    def OnEditorShown(self, evt):
        if evt.GetRow() == 6 and evt.GetCol() == 3 and \
                wx.MessageBox("Are you sure you wish to edit this cell?",
                              "Checking", wx.YES_NO) == wx.NO:
            evt.Veto()
            return
        print("OnEditorShown: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnEditorHidden(self, evt):
        if evt.GetRow() == 6 and evt.GetCol() == 3 and \
                wx.MessageBox("Are you sure you wish to finish editing this cell?",
                              "Checking", wx.YES_NO) == wx.NO:
            evt.Veto()
            return
        print("OnEditorHidden: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnEditorCreated(self, evt):
        print("OnEditorCreated: (%d, %d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetControl()))

    def add_history(self, change):
        self.history.append(change)

    def get_selection(self):
        """
        Returns selected range's start_row, start_col, end_row, end_col
        If there is no selection, returns selected cell's start_row=end_row, start_col=end_col
        """
        if not len(self.GetSelectionBlockTopLeft()):
            selected_columns = self.GetSelectedCols()
            selected_rows = self.GetSelectedRows()
            if selected_columns:
                start_col = selected_columns[0]
                end_col = selected_columns[-1]
                start_row = 0
                end_row = self.GetNumberRows() - 1
            elif selected_rows:
                start_row = selected_rows[0]
                end_row = selected_rows[-1]
                start_col = 0
                end_col = self.GetNumberCols() - 1
            else:
                start_row = end_row = self.GetGridCursorRow()
                start_col = end_col = self.GetGridCursorCol()
        elif len(self.GetSelectionBlockTopLeft()) > 1:
            wx.MessageBox("Multiple selections are not supported", "Warning")
            return []
        else:
            start_row, start_col = self.GetSelectionBlockTopLeft()[0]
            end_row, end_col = self.GetSelectionBlockBottomRight()[0]

        return [start_row, start_col, end_row, end_col]

    def get_selected_cells(self):
        # returns a list of selected cells
        selection = self.get_selection()
        if not selection:
            return

        start_row, start_col, end_row, end_col = selection
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                yield [row, col]

    def onCopy(self, event):
        """
        Copies range of selected cells to clipboard.
        """

        selection = self.get_selection()
        if not selection:
            return []
        start_row, start_col, end_row, end_col = selection

        data = u''

        rows = range(start_row, end_row + 1)
        for row in rows:
            columns = range(start_col, end_col + 1)
            for idx, column in enumerate(columns, 1):
                if idx == len(columns):
                    # if we are at the last cell of the row, add new line instead
                    data += self.GetCellValue(row, column) + "\n"
                else:
                    data += self.GetCellValue(row, column) + "\t"

        text_data_object = wx.TextDataObject()
        text_data_object.SetText(data)

        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(text_data_object)
            wx.TheClipboard.Close()
        else:
            wx.MessageBox("Can'thread_continuous open the clipboard", "Warning")

    def onPaste(self, event):
        if not wx.TheClipboard.Open():
            wx.MessageBox("Can'thread_continuous open the clipboard", "Warning")
            return False

        clipboard = wx.TextDataObject()
        wx.TheClipboard.GetData(clipboard)
        wx.TheClipboard.Close()
        data = clipboard.GetText()
        if data[-1] == "\n":
            data = data[:-1]

        try:
            cells = self.get_selected_cells()
            cell = next(cells)
        except StopIteration:
            return False

        start_row = end_row = cell[0]
        start_col = end_col = cell[1]
        max_row = self.GetNumberRows()
        max_col = self.GetNumberCols()

        history = []
        out_of_range = False

        for row, line in enumerate(data.split("\n")):
            target_row = start_row + row
            if not (0 <= target_row < max_row):
                out_of_range = True
                break

            if target_row > end_row:
                end_row = target_row

            for col, value in enumerate(line.split("\t")):
                target_col = start_col + col
                if not (0 <= target_col < max_col):
                    out_of_range = True
                    break

                if target_col > end_col:
                    end_col = target_col

                # save previous value of the cell for undo
                history.append([target_row, target_col, {"value": self.GetCellValue(target_row, target_col)}])

                self.SetCellValue(target_row, target_col, value)

        self.SelectBlock(start_row, start_col, end_row, end_col)  # select pasted range
        if out_of_range:
            wx.MessageBox("Pasted data is out of Grid range", "Warning")

        self.add_history({"type": "change", "cells": history})

    def onDelete(self, e):
        cells = []
        for row, col in self.get_selected_cells():
            attributes = {
                "value": self.GetCellValue(row, col),
                "alignment": self.GetCellAlignment(row, col)
            }
            cells.append((row, col, attributes))
            self.SetCellValue(row, col, "")

        self.add_history({"type": "delete", "cells": cells})

    def onCut(self, e):
        self.onCopy(e)
        self.onDelete(e)

    def retrieveList(self):
        """
        Copies range of selected cells to clipboard.
        """

        selection = self.get_selection()
        if not selection:
            return []
        start_row, start_col, end_row, end_col = selection

        data = u''
        list_row = []
        list_data = []
        rows = range(start_row, end_row + 1)
        for row in rows:
            columns = range(start_col, end_col + 1)
            for idx, column in enumerate(columns, 1):
                if idx == len(columns):
                    # if we are at the last cell of the row, add new line instead
                    list_row.append(self.GetCellValue(row, column))
                    list_data.append(list_row)
                    list_row = []
                else:
                    list_row.append(self.GetCellValue(row, column))

        return list_data

    def write_list_to_row(self, row=0, data=None):
        if data is not None:
            if row >= 0:
                if row >= self.GetNumberRows() - 1:
                    self.AppendRows(5)
                for col, item in enumerate(data):
                    self.SetCellValue(row, col, str(item))
            else:
                print('row must be in range greater than 0')
        else:
            print('No data to write to grid!')
            pass


class MyApp(wx.App):
    def OnInit(self):
        self.frame = TestFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True

    def get_test_frame(self):
        return self.frame


def main():
    app = MyApp(0)
    app.MainLoop()


if __name__ == "__main__":
    main()
    # bkpts = apply_user_limits(create_breakpoints('dualoutput_pts.csv'), imax=120e-3, fmin=65, fmax=65, pmax=0)
    # bkpts.to_csv('breakpoints.csv', sep=',', index=False)  # write to csv
