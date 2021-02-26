from grid_enhanced import *
from dual_output_test import *

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


class TestFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1384, 584))

        self.T = Test
        self.thread = threading.Thread()
        self.thread.daemon = True

        self.row = 0
        self.prevLine = ''
        self.line = ''
        self.table = {}
        self.overlay = {}
        self.ax = None
        self.x, self.y = [0.], [[0.]]
        self.flag_complete = False
        self.prompt = True

        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.panel_2 = wx.Panel(self.panel_1, wx.ID_ANY)
        self.text_ctrl_9 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_10 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_11 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_1 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_2 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "1")  # 1020
        self.text_ctrl_3 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_4 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "2")  # 29
        self.text_ctrl_5 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_6 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")  # 30000
        self.text_ctrl_7 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")
        self.text_ctrl_8 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "0")  # 270
        self.text_ctrl_12 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "15")

        self.btn_run = wx.Button(self.panel_2, wx.ID_ANY, "Start")
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
        label_15 = wx.StaticText(self.panel_2, wx.ID_ANY, "f8588A (Current)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
        label_15.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_15, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        grid_sizer_1.Add(self.text_ctrl_10, (2, 1), (1, 3), wx.ALL, 5)
        label_16 = wx.StaticText(self.panel_2, wx.ID_ANY, "f5790A (Voltage)", style=wx.ALIGN_CENTER | wx.ALIGN_RIGHT)
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
        self.toggle_ctrl()
        self.flag_complete = False

        test = Test(self)
        self.thread = threading.Thread(target=test.run, args=(self.get_values(),))
        self.thread.start()

    def toggle_ctrl(self):
        if self.text_ctrl_1.IsEnabled():
            self.text_ctrl_1.Enable(False)
            self.text_ctrl_2.Enable(False)
            self.text_ctrl_3.Enable(False)
            self.text_ctrl_4.Enable(False)
            self.text_ctrl_5.Enable(False)
            self.text_ctrl_6.Enable(False)
            self.text_ctrl_7.Enable(False)
            self.text_ctrl_8.Enable(False)
            self.text_ctrl_12.Enable(False)
            self.btn_defaults.Enable(False)
            self.btn_run.Enable(False)
            self.btn_run.SetLabel('Running')
        else:
            self.text_ctrl_1.Enable(True)
            self.text_ctrl_2.Enable(True)
            self.text_ctrl_3.Enable(True)
            self.text_ctrl_4.Enable(True)
            self.text_ctrl_5.Enable(True)
            self.text_ctrl_6.Enable(True)
            self.text_ctrl_7.Enable(True)
            self.text_ctrl_8.Enable(True)
            self.text_ctrl_12.Enable(True)
            self.btn_defaults.Enable(True)
            self.btn_run.Enable(True)
            self.btn_run.SetLabel('Start')

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
        self.text_ctrl_10.SetValue(idn_dict['DMM01'])  # current f8588A
        self.text_ctrl_11.SetValue(idn_dict['DMM02'])  # voltage f8588A

    def show_wiring_dialog(self, state):
        wx.CallAfter(self._open_dialog, state)
        while self.prompt:
            pass
        print('Closed wiring dialog.')
        self.prompt = True

    def _open_dialog(self, config):
        dlg = TestDialog(self, config, None, wx.ID_ANY, "")
        dlg.ShowModal()
        dlg.Destroy()
        self.prompt = False

    def write_header(self, header):
        if not self.table:
            self.table = {key: [] for key in header}
        else:
            self.table = {header[col]: self.table[key] for col, key in enumerate(self.table.keys())}
        header = self.table.keys()

        self.grid_1.write_list_to_row(self.row, header)
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
