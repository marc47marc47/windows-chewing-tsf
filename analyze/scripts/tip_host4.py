"""Drive the legacy Microsoft Bopomofo TIP directly (ground truth for I11).

msctf refuses to route keys to this TIP (its machine-level profile is disabled and msctf falls back to the
default Chewing TIP), so we bypass msctf routing: the TIP is activated manually with a *proxy* ITfThreadMgr
that forwards everything to the real thread manager except ITfKeystrokeMgr, which we implement so that the
TIP's ITfKeyEventSink registration can be captured and called directly.  Composition text lands in an
in-memory ITextStoreACP (tip_host2.Store).  Only this process is affected; user data is only read.
"""
import ctypes as C
import json
import re
import sys
from ctypes import wintypes as W

import tip_host2 as H
from tip_host2 import GUID, GK, guid, vcall, pump, u, ole, Store, TIP_CLSID, IID

IID_KEYSINK = '{AA80E7F5-2021-11D2-93E0-0060B067B86E}'
GK['KSM'] = guid(IID['KSM']).key()
GK['TM'] = guid('{AA80E801-2021-11D2-93E0-0060B067B86E}').key()
GK['KEYSINK'] = guid(IID_KEYSINK).key()
IID_UIMGR = '{EA1EA135-19DF-11D7-A6D2-00065B84435C}'
IID_CANDELEM = '{EA1EA138-19DF-11D7-A6D2-00065B84435C}'
GK['UIMGR'] = guid(IID_UIMGR).key()
V = C.c_void_p
P = C.POINTER


class FakeCom:
    """A COM object whose vtable entries are Python callbacks."""

    def __init__(self, specs):
        self.protos = [C.WINFUNCTYPE(r, *a) for r, a, _ in specs]
        self.cbs = [p(f) for p, (_, _, f) in zip(self.protos, specs)]
        self.arr = (V * len(self.cbs))(*[C.cast(c, V) for c in self.cbs])
        self.obj = V(C.addressof(self.arr))
        self.ptr = V(C.addressof(self.obj))


class Host:
    def __init__(self, real_tm):
        self.real = real_tm
        self.sink = None
        self.advised = []
        H_ = C.c_long
        # fake ITfKeystrokeMgr
        ks = [(H_, [V, P(GUID), P(V)], self.ks_qi), (C.c_ulong, [V], lambda s: 2), (C.c_ulong, [V], lambda s: 1),
              (H_, [V, C.c_uint32, V, C.c_int], self.advise_sink),
              (H_, [V, C.c_uint32], lambda s, t: 0),
              (H_, [V, P(GUID)], lambda s, g: 1),
              (H_, [V, C.c_size_t, C.c_ssize_t, P(C.c_int)], lambda s, w, l, e: 0),
              (H_, [V, C.c_size_t, C.c_ssize_t, P(C.c_int)], lambda s, w, l, e: 0),
              (H_, [V, C.c_size_t, C.c_ssize_t, P(C.c_int)], lambda s, w, l, e: 0),
              (H_, [V, C.c_size_t, C.c_ssize_t, P(C.c_int)], lambda s, w, l, e: 0)] + \
             [(H_, [V, V, V, V, V], lambda *a: 0) for _ in range(7)]
        self.ks = FakeCom(ks)
        self.elements = {}
        self.next_id = 1
        self.events = []
        ui = [(H_, [V, P(GUID), P(V)], self.ui_qi), (C.c_ulong, [V], lambda s: 2), (C.c_ulong, [V], lambda s: 1),
              (H_, [V, V, P(C.c_int), P(C.c_uint32)], self.ui_begin),
              (H_, [V, C.c_uint32], self.ui_update),
              (H_, [V, C.c_uint32], self.ui_end),
              (H_, [V, C.c_uint32, P(V)], self.ui_get),
              (H_, [V, P(V)], lambda s, p: -2147467263)]
        self.ui = FakeCom(ui)
        # proxy ITfThreadMgr: methods 3..13 forward to the real thread manager
        tm = [(H_, [V, P(GUID), P(V)], self.tm_qi), (C.c_ulong, [V], lambda s: 2), (C.c_ulong, [V], lambda s: 1)]
        for idx in range(3, 14):
            tm.append((H_, [V, V, V, V], self.forward(idx)))
        self.tm = FakeCom(tm)

    def forward(self, idx):
        def f(this, a, b, c):
            return vcall(self.real, idx, V, V, V)(self.real, a, b, c)
        return f

    def ui_qi(self, this, riid, ppv):
        if riid.contents.key() in (GK['UIMGR'], GK['UNK']):
            ppv[0] = self.ui.ptr.value
            return 0
        ppv[0] = None
        return -2147467262

    def ui_begin(self, this, elem, pshow, pid):
        e = V(elem)
        vcall(e, 1, V)(e)    # AddRef: keep the element alive
        i = self.next_id
        self.next_id += 1
        self.elements[i] = e
        self.events.append(('begin', i))
        if pshow:
            pshow[0] = 0     # we own the UI: the TIP must not draw its own window
        pid[0] = i
        return 0

    def ui_update(self, this, i):
        self.events.append(('update', i))
        return 0

    def ui_end(self, this, i):
        self.events.append(('end', i))
        return 0

    def ui_get(self, this, i, pp):
        e = self.elements.get(i)
        pp[0] = e.value if e else None
        return 0 if e else -2147024809

    def tm_qi(self, this, riid, ppv):
        k = riid.contents.key()
        if k == GK['UIMGR']:
            ppv[0] = self.ui.ptr.value
            return 0
        if k == GK['KSM']:
            ppv[0] = self.ks.ptr.value
            return 0
        if k in (GK['TM'], GK['UNK']):
            ppv[0] = self.tm.ptr.value
            return 0
        return vcall(self.real, 0, P(GUID), P(V))(self.real, riid, ppv)

    def ks_qi(self, this, riid, ppv):
        if riid.contents.key() in (GK['KSM'], GK['UNK']):
            ppv[0] = self.ks.ptr.value
            return 0
        ppv[0] = None
        return -2147467262

    def advise_sink(self, this, tid, punk, foreground):
        s = V()
        hr = vcall(V(punk), 0, P(GUID), P(V))(V(punk), C.byref(guid(IID_KEYSINK)), C.byref(s))
        self.advised.append((tid, hr, bool(foreground)))
        if hr == 0:
            self.sink = s
        return 0


def modules():
    k32 = C.WinDLL('kernel32')
    ps = C.WinDLL('psapi')
    k32.GetCurrentProcess.restype = W.HANDLE
    ps.EnumProcessModulesEx.argtypes = (W.HANDLE, P(W.HMODULE), W.DWORD, P(W.DWORD), W.DWORD)
    ps.GetModuleFileNameExW.argtypes = (W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD)
    a = (W.HMODULE * 4096)()
    n = W.DWORD()
    ps.EnumProcessModulesEx(k32.GetCurrentProcess(), a, C.sizeof(a), C.byref(n), 3)
    out = []
    for m in a[:n.value // 8]:
        b = C.create_unicode_buffer(1024)
        ps.GetModuleFileNameExW(k32.GetCurrentProcess(), m, b, 1024)
        out.append(b.value)
    return out


class Sess:
    pass


def start_session(clsid=None):
    ole.CoInitializeEx(None, 2)
    s = Sess()
    s.tm = V()
    msctf = C.WinDLL('msctf')
    msctf.TF_CreateThreadMgr(C.byref(s.tm))
    s.cid = C.c_uint32()
    vcall(s.tm, 3, P(C.c_uint32))(s.tm, C.byref(s.cid))
    s.hwnd = u.CreateWindowExW(0, 'EDIT', '', 0x10CF0000 | 0x0004, 100, 100, 600, 200, None, None, None, None)
    u.ShowWindow(s.hwnd, 5)
    u.PostMessageW(s.hwnd, 0x0050, 0, 0x04040404)
    pump(0.3)
    s.store = Store(s.hwnd)
    dm = V()
    vcall(s.tm, 5, P(V))(s.tm, C.byref(dm))
    s.ctx = V()
    cookie = C.c_uint32()
    vcall(dm, 3, C.c_uint32, C.c_uint32, V, P(V), P(C.c_uint32))(dm, s.cid.value, 0, s.store.ptr, C.byref(s.ctx), C.byref(cookie))
    vcall(dm, 4, V)(dm, s.ctx)
    vcall(s.tm, 8, V)(s.tm, dm)
    s.dm = dm
    s.host = Host(s.tm)
    s.tip = V()
    s.log_hr = ole.CoCreateInstance(C.byref(guid(clsid or TIP_CLSID)), None, 1, C.byref(guid(IID['TIP'])), C.byref(s.tip))
    vcall(s.tip, 3, V, C.c_uint32)(s.tip, s.host.tm.ptr, s.cid.value)
    pump(1.0)
    if not s.host.sink:
        raise RuntimeError('TIP key sink was not captured')
    return s


def send_key(s, vk):
    scan = u.MapVirtualKeyW(vk, 0)
    eaten = C.c_int()
    lp = 1 | (scan << 16)
    sink = s.host.sink
    hr = vcall(sink, 6, V, C.c_size_t, C.c_ssize_t, P(C.c_int))(sink, s.ctx, vk, lp, C.byref(eaten))
    e1 = eaten.value
    vcall(sink, 7, V, C.c_size_t, C.c_ssize_t, P(C.c_int))(sink, s.ctx, vk, lp | (1 << 30) | (1 << 31), C.byref(eaten))
    return hr, e1


def settle_text(s, quiet, max_wait):
    """Pump until the text store has been unchanged for `quiet` seconds (or max_wait)."""
    import time as _t
    start = _t.time()
    last = (s.store.text, len(s.store.trace))
    last_change = start
    while _t.time() - start < max_wait:
        pump(0.03)
        cur = (s.store.text, len(s.store.trace))
        if cur != last:
            last, last_change = cur, _t.time()
        elif _t.time() - last_change >= quiet:
            break


def run_keys(s, vks, settle=0.12, max_wait=0.8):
    trace = []
    for vk in vks:
        hr, eaten = send_key(s, vk)
        settle_text(s, settle, max_wait)
        trace.append((vk, eaten, s.store.text))
    settle_text(s, settle * 2, max_wait)
    return dict(text=s.store.text, trace=trace)


def read_candidates(s):
    """Return the full candidate list of the most recently begun, not yet ended, UI element (or None)."""
    live = None
    ended = set()
    for kind, i in s.host.events:
        if kind == 'begin':
            live = i
            ended.discard(i)
        elif kind == 'end':
            ended.add(i)
    if live is None or live in ended:
        return None
    el = s.host.elements[live]
    ce = V()
    if vcall(el, 0, P(GUID), P(V))(el, C.byref(guid(IID_CANDELEM)), C.byref(ce)) != 0:
        return None
    cnt = C.c_uint32()
    vcall(ce, 9, P(C.c_uint32))(ce, C.byref(cnt))
    sel = C.c_uint32()
    vcall(ce, 10, P(C.c_uint32))(ce, C.byref(sel))
    oa = C.WinDLL('oleaut32')
    oa.SysStringLen.argtypes = (V,)
    out = []
    for i in range(cnt.value):
        b = V()
        vcall(ce, 11, C.c_uint32, P(V))(ce, i, C.byref(b))
        out.append(C.wstring_at(b.value, oa.SysStringLen(b)) if b.value else '')
    return dict(count=cnt.value, selection=sel.value, items=out)


IID_EDITSESSION = '{AA80E803-2021-11D2-93E0-0060B067B86E}'
IID_FNRECONV = '{4CEA93C0-0A58-11D3-8DF0-00105A2799B5}'
IID_FNCONV = '{CA5F3E2C-7ADB-4A6F-A3E8-A7B2E1D2F4A5}'
IID_CANDLIST = '{A3AD50FB-9BDB-49E3-A843-6C76520FBF5D}'
IID_CANDSTR = '{581F317E-FD9D-443F-B972-ED00467C5D40}'


def reconversion_candidates(s, start, length, log=None):
    """Ask the TIP (ITfFnReconversion) for the candidate list of text range [start, start+length)."""
    out = {}
    unk = C.c_void_p()
    H_ = C.c_long

    def do_session(this, ec):
        try:
            rng = V()
            hr = vcall(s.ctx, 7, C.c_uint32, P(V))(s.ctx, ec, C.byref(rng))     # GetStart
            out['GetStart'] = hex(hr & 0xffffffff)
            moved = C.c_long()
            if start:
                vcall(rng, 8, C.c_uint32, C.c_long, P(C.c_long), V)(rng, ec, start, C.byref(moved), None)   # ShiftStart
                vcall(rng, 15, C.c_uint32, C.c_int)(rng, ec, 0)                  # Collapse to start
            hr = vcall(rng, 9, C.c_uint32, C.c_long, P(C.c_long), V)(rng, ec, length, C.byref(moved), None)  # ShiftEnd
            out['ShiftEnd'] = (hex(hr & 0xffffffff), moved.value)
            buf = C.create_unicode_buffer(256)
            n = C.c_ulong()
            vcall(rng, 3, C.c_uint32, C.c_uint32, C.c_void_p, C.c_ulong, P(C.c_ulong))(rng, ec, 0, buf, 255, C.byref(n))
            out['range_text'] = buf.value
            prov = V()
            hr = vcall(s.tm, 11, P(GUID), P(V))(s.tm, C.byref(guid(TIP_CLSID)), C.byref(prov))   # GetFunctionProvider
            out['GetFunctionProvider'] = (hex(hr & 0xffffffff), bool(prov.value))
            if prov.value:
                fn = V()
                hr = vcall(prov, 5, P(GUID), P(GUID), P(V))(prov, C.byref(guid('{00000000-0000-0000-0000-000000000000}')), C.byref(guid(IID_FNRECONV)), C.byref(fn))
                out['GetFunction(Reconversion)'] = (hex(hr & 0xffffffff), bool(fn.value))
                if fn.value:
                    cl = V()
                    hr = vcall(fn, 4, V, P(V))(fn, rng, C.byref(cl))               # GetReconversion
                    out['GetReconversion'] = (hex(hr & 0xffffffff), bool(cl.value))
                    if cl.value:
                        cnt = C.c_ulong()
                        vcall(cl, 4, P(C.c_ulong))(cl, C.byref(cnt))                # GetCandidateNum
                        items = []
                        oa = C.WinDLL('oleaut32')
                        oa.SysStringLen.argtypes = (V,)
                        for i in range(cnt.value):
                            cs = V()
                            vcall(cl, 5, C.c_ulong, P(V))(cl, i, C.byref(cs))         # GetCandidate
                            b = V()
                            vcall(cs, 3, P(V))(cs, C.byref(b))                         # ITfCandidateString::GetString
                            items.append(C.wstring_at(b.value, oa.SysStringLen(b)) if b.value else '')
                        out['candidates'] = items
        except Exception as e:      # keep the host alive
            out['error'] = repr(e)
        return 0

    protos = [C.WINFUNCTYPE(H_, V, P(GUID), P(V)), C.WINFUNCTYPE(C.c_ulong, V), C.WINFUNCTYPE(C.c_ulong, V),
              C.WINFUNCTYPE(H_, V, C.c_uint32)]

    def qi(this, riid, ppv):
        ppv[0] = sess_ptr.value
        return 0

    cbs = [protos[0](qi), protos[1](lambda t: 2), protos[2](lambda t: 1), protos[3](do_session)]
    arr = (V * 4)(*[C.cast(c, V) for c in cbs])
    obj = V(C.addressof(arr))
    sess_ptr = V(C.addressof(obj))
    hr_sess = C.c_long()
    r = vcall(s.ctx, 3, C.c_uint32, V, C.c_uint32, P(C.c_long))(s.ctx, s.cid.value, sess_ptr, 0x3, C.byref(hr_sess))   # RequestEditSession TF_ES_SYNC|READ
    out['RequestEditSession'] = (hex(r & 0xffffffff), hex(hr_sess.value & 0xffffffff))
    s._keep = (cbs, arr, obj)
    return out


def reset(s):
    send_key(s, 0x1B)
    settle_text(s, 0.1, 0.6)
    s.store.text = ''
    s.store.sel = (0, 0)
    s.store.trace.clear()


def session(keys, settle=0.8):
    log = {}
    s = start_session()
    log['advised'] = s.host.advised
    vks = [ord(k.upper()) if len(k) == 1 else int(k, 0) for k in keys]
    res = run_keys(s, vks, settle=settle, max_wait=2.0)
    log['modules'] = [m for m in modules() if re.search(r'imtc|imetc|chewing', m, re.I)]
    return log, res['trace'], res['text']


if __name__ == '__main__':
    keys = sys.argv[1:] or ['S', 'U', '3', 'C', 'L', '3']
    log, trace, text = session(keys)
    log['trace'] = trace
    log['final_text'] = text
    print(json.dumps(log, ensure_ascii=False, indent=1))
