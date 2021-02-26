import VisaClient
import time

instruments = {'f5560A': {'address': '129.196.136.130', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
class f5560A_instrument:
    """"""

    def __init__(self):
        super().__init__()
        self.measurement = []
        self.f5560A_IDN = ''
        self.f5560_connected = False
        self.lows = 'open'

    def connect_to_f5560A(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENT -----------------------------------------------------------------------
        self.f5560A = VisaClient.VisaClient(instr_id)  # Fluke 5560A

        if self.f5560A.healthy:
            self.f5560_connected = True
            self.f5560A_IDN = self.f5560A.query('*IDN?')
        else:
            print('\nUnable to connect to the Fluke 5560A. Check software configuration, ensure instrument are in'
                  'appropriate mode, and consider power cycling the suspected instrument\n')

    def setup_source(self):
        self.f5560A.write('*RST')
        time.sleep(1)
        self.f5560A.write('wizard elbereth; ponwiz on')
        self.f5560A.write('COMM_MODE SERIAL, COMP')
        self.f5560A.write('COMM_MODE TELNET, COMP')
        self.f5560A.write('^C')
        time.sleep(0.5)
        self.f5560A.write('MONITOR OFF')
        self.f5560A.write(f'lows {self.lows}')  # lows open is default state

    def set_lows(self, lows='open'):
        read_lows = self.f5560A.query('LOWS?')
        if lows.capitalize() in ('OPEN', 'TIED'):
            if self.lows == read_lows:
                print(f'LOWS currently set to {lows}. No action was performed.')
            else:
                print(f"LOWS {read_lows}, which does not match last known state.\n"
                      f"Proceeding to set LOWS to {lows} and overriding the user's prior selection")
                self.f5560A.write(f'LOWS {lows}')
                self._strobe_f5560A_A7_relays()
                self.lows = lows
        else:
            print("Invalid command. Specify LOWS to be OPEN or TIED\n"
                  f"Currently, LOWS {read_lows}")

    def _strobe_f5560A_A7_relays(self):
        time.sleep(1)
        self.f5560A.write('mod p7p6,#h20,#h0')
        time.sleep(1)
        self.f5560A.write('mod p7p6,#h20,#h20')

    def set_source(self, mode='V', rms=0.0, Ft=0.0):
        try:
            if mode.capitalize() == 'A':
                self.f5560A.write(f'\nout {rms}A, {Ft}Hz')
                time.sleep(2)
                print(f'\nout: {rms}A, {Ft}Hz')
            else:
                self.f5560A.write(f'\nout {rms}V, {Ft}Hz')
                time.sleep(2)
                print(f'\nout: {rms}V, {Ft}Hz')
            time.sleep(1)
        except ValueError:
            raise

    def run_source(self, mode, rms, Ft):
        try:
            self.set_source(mode, rms, Ft)
            self.f5560A.write('oper')
            time.sleep(5)
        except ValueError:
            raise

    def standby_f5560A(self):
        time.sleep(1)
        self.f5560A.write('STBY')
        self.f5560A.write('*WAI')
        time.sleep(1)

    def close_f5560A(self):
        if self.f5560_connected:
            time.sleep(1)
            self.f5560A.close()
            self.f5560_connected = False


# Run
if __name__ == "__main__":
    mode, rms, Ft = 'A', 120e-3, 1000

    instr = f5560A_instrument()
    instr.connect_to_f5560A(instruments)
    instr.setup_source()

    instr.run_source(mode, rms, Ft)
    time.sleep(5)
    instr.close_f5560A()
