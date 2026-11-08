"""主流程与标定共用的游戏操作。"""
import ctypes
from ctypes import wintypes
import pathlib
import time
from jump_native import screenshot, user32
from jump_vision import find_piece, find_target, save_png
from jump_score import read_score

ROOT = pathlib.Path(__file__).resolve().parent
user32.FindWindowW.argtypes = [wintypes.LPCWSTR,wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetClientRect.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.POINT)]


def game_region():
    window = user32.FindWindowW(None,'跳一跳')
    if not window:
        raise ValueError('请先打开跳一跳游戏窗口。')
    rect = wintypes.RECT()
    user32.GetClientRect(window,ctypes.byref(rect))
    origin = wintypes.POINT(0,0)
    user32.ClientToScreen(window,ctypes.byref(origin))
    return origin.x,origin.y,rect.right,rect.bottom


def observe(save=None):
    region = game_region()
    image = screenshot(region)
    if save:
        save_png(ROOT/save,image,region[2],region[3])
    piece,box,score = find_piece(image,region[2],region[3],ROOT/'piece.png')
    target = find_target(image,region[2],region[3],piece,details=True)
    return {'region':region,'piece':piece,'piece_box':box,'template_error':score,
            'score':read_score(image,region[2],region[3]),**target}


def landing_state(save):
    region=game_region()
    image=screenshot(region)
    save_png(ROOT/save,image,region[2],region[3])
    result={'score':read_score(image,region[2],region[3])}
    try:
        result['piece'],result['piece_box'],result['template_error']=find_piece(image,region[2],region[3],ROOT/'piece.png')
    except ValueError:
        result['piece']=None
    return result


def press(seconds):
    left,top,width,height = game_region()
    user32.SetCursorPos(left+width//2,top+int(height*.83))
    user32.mouse_event(0x0002,0,0,0,0)
    begin = time.perf_counter()
    try:
        # 常规 sleep 会多等一小段；最后 2 毫秒按高精度时钟对齐释放时刻。
        deadline=begin+seconds
        time.sleep(max(0,seconds-.002))
        while time.perf_counter()<deadline:
            pass
    finally:
        user32.mouse_event(0x0004,0,0,0,0)
    return time.perf_counter()-begin
