import VisaClient
import time
import numpy as np

instruments = {'f5790B': {'address': '10.205.92.156', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
def to_float(s):
    f = 0.0
    try:
        f = float(s)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        pass
    return f


class f5790B_instrument:
    def __init__(self):
        super().__init__()
        self.measurement = []
        self.f5790B_IDN = ''
        self.f5790B_connected = False

    def connect_to_f5790B(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        self.f5790B = VisaClient.VisaClient(instr_id)  # Fluke 5790B

        if self.f5790B.healthy:
            self.f5790B_connected = True
            try:
                self.f5790B_IDN = self.f5790B.query('*IDN?')
            except ValueError:
                raise
        else:
            print('\nUnable to connect to the Fluke 5790B. Check software configuration, ensure instrument are in'
                  'appropriate mode, and consider power cycling the suspected instrument\n')

    ####################################################################################################################
    def setup_f5790B(self, input_terminal='INPUT1', EXTRIG='OFF', HIRES='ON', EXTGUARD='OFF'):
        """
        :param input_terminal: selects the active input terminal
        :param EXTRIG: 'ON' enables external triggering mode
        :param HIRES: 'ON' enables higher resolution amplitude display
        :param EXTGUARD: 'ON' enables extern GUARD connection
                          ON or 1 set external guard
                          OFF or 0 set internal guard
        :return:
        """
        # Fluke 5790B --------------------------------------------------------------------------------------------------
        self.f5790B.write(f'*RST; INPUT {input_terminal}; EXTRIG {EXTRIG}; HIRES {HIRES}; EXTGUARD {EXTGUARD}')
        time.sleep(1)

    ####################################################################################################################
    def read_voltage(self, input_terminal='', samples=1):
        if input_terminal:
            self.f5790B.write(f'INPUT {input_terminal}')
            self.f5790B.write('TRIG')
            time.sleep(1)

        readings = np.zeros(samples)
        for idx in range(samples):
            readings[idx] = self.f5790B.query('*WAI;VAL?').split(',')[0]
            time.sleep(0.2)

        mean = readings.mean()
        std = np.sqrt(np.mean(abs(readings - mean) ** 2))
        return mean, std

    ####################################################################################################################
    def close_f5790B(self):
        if self.f5790B_connected:
            time.sleep(1)
            self.f5790B.close()
            self.f5790B_connected = False


# Run
if __name__ == "__main__":
    output, mode = 'VOLT', 'AC'
    instr = f5790B_instrument()

    instr.connect_to_f5790B(instruments)
    instr.setup_f5790B(output, mode)

    mean, std = instr.read_voltage(input_terminal='INPUT2', samples=15)
    print(f"\nVoltage: {mean}\nStandard Deviation: {std} Hz")

    instr.setup_f5790B()
