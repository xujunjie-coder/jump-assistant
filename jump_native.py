import ctypes
from ctypes import wintypes
import math
import time


# 按截图中的 405 像素窗口宽度归一化；跳短了增大，跳远了减小。
PRESS_RATIO = 0.003

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.SetProcessDPIAware()

# Windows 接口声明，避免 64 位系统上的句柄被截断。
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, ctypes.c_int, wintypes.HDC,
                       ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("width", wintypes.LONG),
                ("height", wintypes.LONG), ("planes", wintypes.WORD),
                ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                ("image_size", wintypes.DWORD), ("xppm", wintypes.LONG),
                ("yppm", wintypes.LONG), ("colors", wintypes.DWORD),
                ("important", wintypes.DWORD)]


gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                          wintypes.UINT, ctypes.c_void_p,
                          ctypes.POINTER(BitmapInfoHeader), wintypes.UINT]


def screenshot(region):
    """截取游戏区域，返回像素数据；这里只使用 Windows 自带接口。"""
    left, top, width, height = region
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    previous = gdi32.SelectObject(memory, bitmap)
    try:
        gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, 0x00CC0020)
        gdi32.SelectObject(memory, previous)
        header = BitmapInfoHeader()
        header.size = ctypes.sizeof(header)
        header.width, header.height = width, -height
        header.planes, header.bits = 1, 32
        data = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(memory, bitmap, 0, height, data, ctypes.byref(header), 0)
        return data.raw
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)


def pixel(image, width, x, y):
    offset = (y * width + x) * 4
    b, g, r = image[offset:offset + 3]
    return r, g, b
