"""Güncelleyici açık Odak'ı kapatır; kaydedilmemiş formu korur.

Geçici verilerle iki kısa Windows penceresi açar.
"""
import ctypes
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from tools.install_state import stop_running

CHILD = '''
import sys
from pathlib import Path
import app
from PySide6.QtCore import QTimer
from odak.ui import MainWindow
mode=sys.argv.pop(1)
data=Path(sys.argv[sys.argv.index('--data-dir')+1])
anchor=MainWindow.anchor
def position(self):
    anchor(self)
    self.move(70,50)
MainWindow.anchor=position
original=app.QApplication
class CheckApplication(original):
    def __init__(self,*args):
        super().__init__(*args)
        QTimer.singleShot(250,self.ready)
        QTimer.singleShot(15000,self.quit)
    def ready(self):
        root=next(w for w in self.topLevelWidgets() if isinstance(w,MainWindow))
        if mode=='modal':
            def fill():
                self.activeModalWidget().title.setText('Unsaved installer check')
                (data/'ready').write_text('ready')
            QTimer.singleShot(100,fill)
            root.edit_task()
        else:
            (data/'ready').write_text('ready')
app.QApplication=CheckApplication
raise SystemExit(app.main())
'''

user32=ctypes.windll.user32
user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
user32.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)

with tempfile.TemporaryDirectory() as directory:
    for mode in ('normal','modal'):
        data=Path(directory)/mode
        process=subprocess.Popen([sys.executable,'-c',CHILD,mode,'--data-dir',str(data)],cwd=PROJECT,
            env={**os.environ,'QT_QPA_PLATFORM':'windows'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            until=time.monotonic()+8
            while not (data/'ready').exists() and time.monotonic()<until:
                if process.poll() is not None:raise RuntimeError('Check app exited before ready.')
                time.sleep(.04)
            assert (data/'ready').exists()
            if mode=='modal':
                try:stop_running(data)
                except RuntimeError as error:assert 'form' in str(error)
                else:raise AssertionError('An unsaved form must block the update.')
                assert process.poll() is None and (data/'odak.lock').exists()
                pid=int((data/'odak.lock').read_text(encoding='utf-8').splitlines()[0])
                @callback_type
                def close_form(hwnd,_):
                    identity=wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd,ctypes.byref(identity))
                    caption=ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd,caption,len(caption))
                    if identity.value==pid and caption.value=='Yeni görev':
                        user32.PostMessageW(hwnd,0x10,0,0)
                    return True
                user32.EnumWindows(close_form,0)
                time.sleep(.2)
            stop_running(data)
            assert not (data/'odak.lock').exists()
            assert process.wait(timeout=5)==0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
print('Windows updater check: graceful exit, unsaved form preserved and retry after closing the form OK.')
