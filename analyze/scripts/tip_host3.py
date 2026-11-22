"""Host the legacy Microsoft Bopomofo TIP with an in-memory ITextStoreACP and feed it keys.

Ground-truth harness (I11): the real IMTCTIP/IMTCCORE code runs in this process; our text store is
a plain Python string, so composition/commit results can be read back without any UI.
Only this process is affected; user data files are only read.  Windows x64 Python required.
"""
import ctypes as C
import json
import re
import sys
import time
from ctypes import wintypes as W

TIP_CLSID = '{B115690A-EA02-48D5-A231-E3578D2FDF80}'
IID = dict(
    TIP='{AA80E7F7-2021-11D2-93E0-0060B067B86E}', KSM='{AA80E7F0-2021-11D2-93E0-0060B067B86E}',
    TEXTSTORE='{28888FE3-C2A0-483A-A3EA-8CB1CE51FF3D}', SINK='{22D44C94-A419-4542-A272-AE26093ECECF}',
    UNK='{00000000-0000-0000-C000-000000000046}')


class GUID(C.Structure):
    _fields_ = [('a', C.c_uint32), ('b', C.c_uint16), ('c', C.c_uint16), ('d', C.c_ubyte * 8)]

    def key(self):
        return bytes(C.string_at(C.addressof(self), 16))


class SEL(C.Structure):
    _fields_ = [('start', C.c_long), ('end', C.c_long), ('ase', C.c_int), ('interim', C.c_int)]


class TEXTCHANGE(C.Structure):
    _fields_ = [('start', C.c_long), ('oldEnd', C.c_long), ('newEnd', C.c_long)]


ole = C.WinDLL('ole32')
u = C.WinDLL('user32', use_last_error=True)
u.CreateWindowExW.restype = W.HWND
u.CreateWindowExW.argtypes = (W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
                              W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID)


def guid(t):
    g = GUID()
    ole.CLSIDFromString(C.c_wchar_p(t), C.byref(g))
    return g


GK = {k: guid(v).key() for k, v in IID.items()}


def vcall(obj, index, *argtypes):
    vt = C.cast(C.cast(obj, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))
    return C.WINFUNCTYPE(C.c_long, C.c_void_p, *argtypes)(vt[index])


def pump(sec):
    msg = W.MSG()
    end = time.time() + sec
    while time.time() < end:
        while u.PeekMessageW(C.byref(msg), None, 0, 0, 1):
            u.TranslateMessage(C.byref(msg))
            u.DispatchMessageW(C.byref(msg))
        time.sleep(0.01)


class Store:
    """Minimal ITextStoreACP backed by a Python string."""
    def __init__(self, hwnd):
        self.text = ''
        self.sel = (0, 0)
        self.sink = None
        self.hwnd = hwnd
        self.lock = 0
        self.trace = []
        self.keep = []
        P = C.POINTER
        W_ = C.WINFUNCTYPE
        H = C.c_long
        V = C.c_void_p
        proto = [
            ('QueryInterface', H, [V, P(GUID), P(V)], self.qi),
            ('AddRef', C.c_ulong, [V], lambda s: 2),
            ('Release', C.c_ulong, [V], lambda s: 1),
            ('AdviseSink', H, [V, P(GUID), V, C.c_ulong], self.advise),
            ('UnadviseSink', H, [V, V], lambda s, p: 0),
            ('RequestLock', H, [V, C.c_ulong, P(H)], self.request_lock),
            ('GetStatus', H, [V, V], self.get_status),
            ('QueryInsert', H, [V, C.c_long, C.c_long, C.c_ulong, P(C.c_long), P(C.c_long)], self.query_insert),
            ('GetSelection', H, [V, C.c_ulong, C.c_ulong, P(SEL), P(C.c_ulong)], self.get_selection),
            ('SetSelection', H, [V, C.c_ulong, P(SEL)], self.set_selection),
            ('GetText', H, [V, C.c_long, C.c_long, V, C.c_ulong, P(C.c_ulong), V, C.c_ulong, P(C.c_ulong), P(C.c_long)], self.get_text),
            ('SetText', H, [V, C.c_ulong, C.c_long, C.c_long, C.c_wchar_p, C.c_ulong, P(TEXTCHANGE)], self.set_text),
            ('GetFormattedText', H, [V, C.c_long, C.c_long, P(V)], lambda *a: -2147467263),
            ('GetEmbedded', H, [V, C.c_long, P(GUID), P(GUID), P(V)], lambda *a: -2147467263),
            ('QueryInsertEmbedded', H, [V, P(GUID), V, P(C.c_int)], lambda *a: -2147467263),
            ('InsertEmbedded', H, [V, C.c_ulong, C.c_long, C.c_long, V, P(TEXTCHANGE)], lambda *a: -2147467263),
            ('InsertTextAtSelection', H, [V, C.c_ulong, C.c_wchar_p, C.c_ulong, P(C.c_long), P(C.c_long), P(TEXTCHANGE)], self.insert_at_sel),
            ('InsertEmbeddedAtSelection', H, [V, C.c_ulong, V, P(C.c_long), P(C.c_long), P(TEXTCHANGE)], lambda *a: -2147467263),
            ('RequestSupportedAttrs', H, [V, C.c_ulong, C.c_ulong, V], lambda *a: 0),
            ('RequestAttrsAtPosition', H, [V, C.c_long, C.c_ulong, V, C.c_ulong], lambda *a: 0),
            ('RequestAttrsTransitioningAtPosition', H, [V, C.c_long, C.c_ulong, V, C.c_ulong], lambda *a: 0),
            ('FindNextAttrTransition', H, [V, C.c_long, C.c_long, C.c_ulong, V, C.c_ulong, P(C.c_long), P(C.c_int), P(C.c_long)], lambda *a: 0),
            ('RetrieveRequestedAttrs', H, [V, C.c_ulong, V, P(C.c_ulong)], self.retrieve_attrs),
            ('GetEndACP', H, [V, P(C.c_long)], self.get_end),
            ('GetActiveView', H, [V, P(C.c_ulong)], self.get_view),
            ('GetACPFromPoint', H, [V, C.c_ulong, V, C.c_ulong, P(C.c_long)], lambda *a: -2147467263),
            ('GetTextExt', H, [V, C.c_ulong, C.c_long, C.c_long, V, P(C.c_int)], self.get_text_ext),
            ('GetScreenExt', H, [V, C.c_ulong, V], self.get_screen_ext),
            ('GetWnd', H, [V, C.c_ulong, P(W.HWND)], self.get_wnd),
        ]
        self.protos = [W_(r, *a) for _, r, a, _ in proto]
        self.cbs = [p(f) for p, (_, _, _, f) in zip(self.protos, proto)]
        self.names = [n for n, *_ in proto]
        arr = (C.c_void_p * len(self.cbs))(*[C.cast(c, C.c_void_p) for c in self.cbs])
        self.vtbl = arr
        self.obj = C.c_void_p(C.addressof(arr))
        self.ptr = C.c_void_p(C.addressof(self.obj))

    # ---- COM
    def qi(self, this, riid, ppv):
        k = riid.contents.key()
        if k in (GK['UNK'], GK['TEXTSTORE']):
            ppv[0] = self.ptr.value
            return 0
        ppv[0] = None
        return -2147467262

    def advise(self, this, riid, punk, mask):
        self.sink = C.c_void_p(punk)
        sink = C.c_void_p()
        # QI to ITextStoreACPSink
        hr = vcall(self.sink, 0, C.POINTER(GUID), C.POINTER(C.c_void_p))(self.sink, C.byref(guid(IID['SINK'])), C.byref(sink))
        if hr == 0:
            self.sink = sink
        return 0

    def request_lock(self, this, flags, phr):
        self.lock = flags
        if self.sink:
            hr = vcall(self.sink, 8, C.c_ulong)(self.sink, flags)   # OnLockGranted
            phr[0] = hr
        else:
            phr[0] = -2147220992
        self.lock = 0
        return 0

    def get_status(self, this, p):
        C.memmove(p, (C.c_ulong * 2)(0, 0), 8)
        return 0

    def query_insert(self, this, s, e, cch, rs, re_):
        rs[0] = s
        re_[0] = e
        return 0

    def get_selection(self, this, idx, count, p, fetched):
        if idx != 0xFFFFFFFF and idx != 0:
            fetched[0] = 0
            return -2147220983
        p[0] = SEL(self.sel[0], self.sel[1], 1, 0)
        fetched[0] = 1
        return 0

    def set_selection(self, this, count, p):
        self.sel = (p[0].start, p[0].end)
        return 0

    def get_text(self, this, s, e, buf, cch, ret, runinfo, crun, runret, nxt):
        end = len(self.text) if e == -1 else e
        chunk = self.text[s:end][:cch]
        if buf and cch:
            C.memmove(buf, (chunk + '\0').encode('utf-16le'), len(chunk) * 2)
        ret[0] = len(chunk)
        if runret:
            runret[0] = 0
        nxt[0] = s + len(chunk)
        return 0

    def _apply(self, s, e, text, tc):
        self.text = self.text[:s] + text + self.text[e:]
        if tc:
            tc[0] = TEXTCHANGE(s, e, s + len(text))
        self.sel = (s + len(text), s + len(text))
        self.trace.append(('text', self.text))

    def set_text(self, this, flags, s, e, text, cch, tc):
        e = len(self.text) if e == -1 else e
        self._apply(s, e, (text or '')[:cch], tc)
        return 0

    def insert_at_sel(self, this, flags, text, cch, rs, re_, tc):
        s, e = self.sel
        t = (text or '')[:cch]
        self._apply(s, e, t, tc)
        rs[0], re_[0] = s, s + len(t)
        return 0

    def retrieve_attrs(self, this, n, p, fetched):
        fetched[0] = 0
        return 0

    def get_end(self, this, p):
        p[0] = len(self.text)
        return 0

    def get_view(self, this, p):
        p[0] = 1
        return 0

    def get_text_ext(self, this, vc, s, e, rect, clipped):
        C.memmove(rect, (C.c_long * 4)(100, 100, 200, 130), 16)
        clipped[0] = 0
        return 0

    def get_screen_ext(self, this, vc, rect):
        C.memmove(rect, (C.c_long * 4)(0, 0, 800, 600), 16)
        return 0

    def get_wnd(self, this, vc, ph):
        ph[0] = self.hwnd
        return 0


def main():
    log = {}
    ole.CoInitializeEx(None, 2)
    tm = C.c_void_p()
    msctf = C.WinDLL('msctf')
    log['TF_CreateThreadMgr'] = hex(msctf.TF_CreateThreadMgr(C.byref(tm)) & 0xffffffff)
    cid = C.c_uint32()
    log['ThreadMgr.Activate'] = hex(vcall(tm, 3, C.POINTER(C.c_uint32))(tm, C.byref(cid)) & 0xffffffff)
    hwnd = u.CreateWindowExW(0, 'EDIT', '', 0x10CF0000 | 0x0004, 100, 100, 600, 200, None, None, None, None)
    u.ShowWindow(hwnd, 5)
    u.SetForegroundWindow(hwnd)
    u.PostMessageW(hwnd, 0x0050, 0, 0x04040404)
    pump(0.5)
    store = Store(hwnd)
    dm = C.c_void_p()
    log['CreateDocumentMgr'] = hex(vcall(tm, 5, C.POINTER(C.c_void_p))(tm, C.byref(dm)) & 0xffffffff)
    ctx = C.c_void_p()
    cookie = C.c_uint32()
    log['CreateContext'] = hex(vcall(dm, 3, C.c_uint32, C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p), C.POINTER(C.c_uint32))(
        dm, cid.value, 0, store.ptr, C.byref(ctx), C.byref(cookie)) & 0xffffffff)
    log['Push'] = hex(vcall(dm, 4, C.c_void_p)(dm, ctx) & 0xffffffff)
    log['ThreadMgr.SetFocus'] = hex(vcall(tm, 8, C.c_void_p)(tm, dm) & 0xffffffff)
    tip = C.c_void_p()
    log['CoCreateInstance(TIP)'] = hex(ole.CoCreateInstance(C.byref(guid(TIP_CLSID)), None, 1, C.byref(guid(IID['TIP'])), C.byref(tip)) & 0xffffffff)
    log['TIP.Activate'] = hex(vcall(tip, 3, C.c_void_p, C.c_uint32)(tip, tm, cid.value) & 0xffffffff)
    pump(1.0)
    ks = C.c_void_p()
    log['QI ITfKeyEventSink'] = hex(vcall(tip, 0, C.POINTER(GUID), C.POINTER(C.c_void_p))(tip, C.byref(guid('{AA80E7F5-2021-11D2-93E0-0060B067B86E}')), C.byref(ks)) & 0xffffffff)
    if ks.value:
        log['Sink.OnSetFocus'] = hex(vcall(ks, 3, C.c_int)(ks, 1) & 0xffffffff)
    ksm = C.c_void_p()
    vcall(tm, 0, C.POINTER(GUID), C.POINTER(C.c_void_p))(tm, C.byref(guid(IID['KSM'])), C.byref(ksm))
    fg = GUID()
    log['GetForeground'] = hex(vcall(ksm, 5, C.POINTER(GUID))(ksm, C.byref(fg)) & 0xffffffff)
    log['foreground_clsid'] = '{%08X-%04X-%04X-%s-%s}' % (fg.a, fg.b, fg.c, bytes(fg.d[:2]).hex().upper(), bytes(fg.d[2:]).hex().upper())
    keys = sys.argv[1:] or ['S', 'U', '3', 'C', 'L', '3']
    out = []
    for k in keys:
        vk = ord(k.upper()) if len(k) == 1 else int(k, 0)
        scan = u.MapVirtualKeyW(vk, 0)
        eaten = C.c_int()
        lp = 1 | (scan << 16)
        hr = vcall(ks, 6, C.c_void_p, C.c_size_t, C.c_ssize_t, C.POINTER(C.c_int))(ks, ctx, vk, lp, C.byref(eaten))     # OnKeyDown
        vcall(ks, 7, C.c_void_p, C.c_size_t, C.c_ssize_t, C.POINTER(C.c_int))(ks, ctx, vk, lp | (1 << 30) | (1 << 31), C.byref(eaten))  # OnKeyUp
        pump(0.3)
        out.append((k, hex(hr & 0xffffffff), eaten.value, store.text))
    log['keys'] = out
    pump(1.0)
    k32 = C.WinDLL('kernel32'); ps = C.WinDLL('psapi')
    k32.GetCurrentProcess.restype = W.HANDLE
    ps.EnumProcessModulesEx.argtypes = (W.HANDLE, C.POINTER(W.HMODULE), W.DWORD, C.POINTER(W.DWORD), W.DWORD)
    ps.GetModuleFileNameExW.argtypes = (W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD)
    a = (W.HMODULE * 4096)(); n = W.DWORD()
    ps.EnumProcessModulesEx(k32.GetCurrentProcess(), a, C.sizeof(a), C.byref(n), 3)
    mods = []
    for m in a[:n.value // 8]:
        b = C.create_unicode_buffer(1024); ps.GetModuleFileNameExW(k32.GetCurrentProcess(), m, b, 1024); mods.append(b.value)
    log['tip_modules'] = [m for m in mods if re.search(r'imtc|imetc|chewing', m, re.I)]
    log['final_text'] = store.text
    log['trace_tail'] = store.trace[-5:]
    print(json.dumps(log, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
