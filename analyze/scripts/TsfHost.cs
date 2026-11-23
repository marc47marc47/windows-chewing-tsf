// Minimal TSF host: drives the INSTALLED Chewing TIP through msctf's normal routing and records the text it writes.
// Build: csc /nologo /out:tsfhost.exe TsfHost.cs     Run: tsfhost.exe KEYS   (KEYS like hk4g4bp4j4, '_' = Space)
// Only this process is affected (ActivateProfile FORPROCESS); the TIP reads the user's registry config.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

[StructLayout(LayoutKind.Sequential)] struct TS_SELECTION_ACP { public int start, end; public int ase; public int interim; }
[StructLayout(LayoutKind.Sequential)] struct TS_TEXTCHANGE { public int start, oldEnd, newEnd; }
[StructLayout(LayoutKind.Sequential)] struct TS_STATUS { public uint dynamic, statik; }
[StructLayout(LayoutKind.Sequential)] struct RECT { public int l, t, r, b; }
[StructLayout(LayoutKind.Sequential)] struct POINT { public int x, y; }
[StructLayout(LayoutKind.Sequential)] struct TS_RUNINFO { public uint cch, type; }
[StructLayout(LayoutKind.Sequential)] struct MSG { public IntPtr hwnd; public uint message; public UIntPtr wParam; public IntPtr lParam; public uint time; public POINT pt; }

[ComImport, Guid("22D44C94-A419-4542-A272-AE26093ECECF"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITextStoreACPSink {
    void OnTextChange(uint f, ref TS_TEXTCHANGE c); void OnSelectionChange(); void OnLayoutChange(int code, uint view);
    void OnStatusChange(uint f); void OnAttrsChange(int s, int e, uint n, IntPtr a); void OnLockGranted(uint f);
    void OnStartEditTransaction(); void OnEndEditTransaction();
}

[ComImport, Guid("28888FE3-C2A0-483A-A3EA-8CB1CE51FF3D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITextStoreACP {
    void AdviseSink(ref Guid riid, [MarshalAs(UnmanagedType.IUnknown)] object punk, uint mask);
    void UnadviseSink([MarshalAs(UnmanagedType.IUnknown)] object punk);
    void RequestLock(uint flags, out int hrSession);
    void GetStatus(out TS_STATUS st);
    void QueryInsert(int s, int e, uint cch, out int rs, out int re);
    void GetSelection(uint idx, uint count, [Out, MarshalAs(UnmanagedType.LPArray, SizeParamIndex = 1)] TS_SELECTION_ACP[] sel, out uint fetched);
    void SetSelection(uint count, [In, MarshalAs(UnmanagedType.LPArray, SizeParamIndex = 0)] TS_SELECTION_ACP[] sel);
    void GetText(int s, int e, IntPtr plain, uint cchReq, out uint cchRet, IntPtr runs, uint runReq, out uint runRet, out int next);
    void SetText(uint flags, int s, int e, [MarshalAs(UnmanagedType.LPWStr)] string text, uint cch, out TS_TEXTCHANGE tc);
    void GetFormattedText(int s, int e, [MarshalAs(UnmanagedType.IUnknown)] out object o);
    void GetEmbedded(int pos, ref Guid g, ref Guid riid, [MarshalAs(UnmanagedType.IUnknown)] out object o);
    void QueryInsertEmbedded(ref Guid g, IntPtr fmt, [MarshalAs(UnmanagedType.Bool)] out bool ok);
    void InsertEmbedded(uint flags, int s, int e, [MarshalAs(UnmanagedType.IUnknown)] object o, out TS_TEXTCHANGE tc);
    void InsertTextAtSelection(uint flags, [MarshalAs(UnmanagedType.LPWStr)] string text, uint cch, out int rs, out int re, out TS_TEXTCHANGE tc);
    void InsertEmbeddedAtSelection(uint flags, [MarshalAs(UnmanagedType.IUnknown)] object o, out int rs, out int re, out TS_TEXTCHANGE tc);
    void RequestSupportedAttrs(uint f, uint n, IntPtr a);
    void RequestAttrsAtPosition(int pos, uint n, IntPtr a, uint f);
    void RequestAttrsTransitioningAtPosition(int pos, uint n, IntPtr a, uint f);
    void FindNextAttrTransition(int s, int halt, uint n, IntPtr a, uint f, out int next, [MarshalAs(UnmanagedType.Bool)] out bool found, out int off);
    void RetrieveRequestedAttrs(uint n, IntPtr a, out uint fetched);
    void GetEndACP(out int acp);
    void GetActiveView(out uint view);
    void GetACPFromPoint(uint view, ref POINT pt, uint f, out int acp);
    void GetTextExt(uint view, int s, int e, out RECT r, [MarshalAs(UnmanagedType.Bool)] out bool clipped);
    void GetScreenExt(uint view, out RECT r);
    void GetWnd(uint view, out IntPtr hwnd);
}

[ComImport, Guid("AA80E801-2021-11D2-93E0-0060B067B86E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfThreadMgr {
    void Activate(out uint tid); void Deactivate(); void CreateDocumentMgr(out ITfDocumentMgr dm);
    void EnumDocumentMgrs(out IntPtr e); void GetFocus(out ITfDocumentMgr dm); void SetFocus(ITfDocumentMgr dm);
    void AssociateFocus(IntPtr hwnd, ITfDocumentMgr n, out ITfDocumentMgr prev); void IsThreadFocus([MarshalAs(UnmanagedType.Bool)] out bool f);
    void GetFunctionProvider(ref Guid clsid, out IntPtr p); void EnumFunctionProviders(out IntPtr e); void GetGlobalCompartment(out IntPtr c);
}

[ComImport, Guid("AA80E7F4-2021-11D2-93E0-0060B067B86E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfDocumentMgr {
    void CreateContext(uint tid, uint flags, [MarshalAs(UnmanagedType.IUnknown)] object punk, out ITfContext ic, out uint ecTextStore);
    void Push(ITfContext ic); void Pop(uint flags); void GetTop(out ITfContext ic); void GetBase(out ITfContext ic); void EnumContexts(out IntPtr e);
}

[ComImport, Guid("7DCF57AC-18AD-438B-824D-979BFFB74B7C"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfCompartmentMgr { void GetCompartment(ref Guid g, out ITfCompartment c); void ClearCompartment(uint tid, ref Guid g); void EnumCompartments(out IntPtr e); }
[ComImport, Guid("BB08F7A9-607A-4384-8623-056892B64371"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfCompartment { void SetValue(uint tid, ref object v); void GetValue(out object v); }

[ComImport, Guid("AA80E7FD-2021-11D2-93E0-0060B067B86E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfContext { void RequestEditSession(uint tid, IntPtr es, uint flags, out int hr); }

[ComImport, Guid("AA80E7F0-2021-11D2-93E0-0060B067B86E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfKeystrokeMgr {
    void AdviseKeyEventSink(uint tid, IntPtr sink, [MarshalAs(UnmanagedType.Bool)] bool fg); void UnadviseKeyEventSink(uint tid);
    void GetForeground(out Guid clsid);
    void TestKeyDown(UIntPtr w, IntPtr l, [MarshalAs(UnmanagedType.Bool)] out bool eaten);
    void TestKeyUp(UIntPtr w, IntPtr l, [MarshalAs(UnmanagedType.Bool)] out bool eaten);
    void KeyDown(UIntPtr w, IntPtr l, [MarshalAs(UnmanagedType.Bool)] out bool eaten);
    void KeyUp(UIntPtr w, IntPtr l, [MarshalAs(UnmanagedType.Bool)] out bool eaten);
}

[ComImport, Guid("71C6E74C-0F28-11D8-A82A-00065B84435C"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfInputProcessorProfileMgr {
    void ActivateProfile(uint type, ushort lang, ref Guid clsid, ref Guid profile, IntPtr hkl, uint flags);
    void DeactivateProfile(uint type, ushort lang, ref Guid clsid, ref Guid profile, IntPtr hkl, uint flags);
    void GetProfile(uint type, ushort lang, ref Guid clsid, ref Guid profile, IntPtr hkl, IntPtr outp);
    void EnumProfiles(ushort lang, out IntPtr e);
    void ReleaseInputProcessor(ref Guid clsid, uint flags);
    void RegisterProfile(ref Guid clsid, ushort lang, ref Guid profile, IntPtr desc, uint c1, IntPtr icon, uint c2, uint idx, IntPtr hkl, uint caps, int enabled, uint flags);
    void UnregisterProfile(ref Guid clsid, ushort lang, ref Guid profile, uint flags);
    void GetActiveProfile(ref Guid cat, IntPtr outp);
}

[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
class Store : ITextStoreACP {
    public string Text = ""; public int Sel = 0; ITextStoreACPSink sink; public IntPtr Hwnd; public List<string> Trace = new List<string>();
    public void AdviseSink(ref Guid riid, object punk, uint mask) { sink = (ITextStoreACPSink)punk; }
    public void UnadviseSink(object punk) { sink = null; }
    public void RequestLock(uint flags, out int hr) { hr = 0; if (sink != null) sink.OnLockGranted(flags); }
    public void GetStatus(out TS_STATUS st) { st.dynamic = 0; st.statik = 0; }
    public void QueryInsert(int s, int e, uint cch, out int rs, out int re) { rs = s; re = e; }
    public void GetSelection(uint idx, uint count, TS_SELECTION_ACP[] sel, out uint fetched) { sel[0].start = Sel; sel[0].end = Sel; sel[0].ase = 1; sel[0].interim = 0; fetched = 1; }
    public void SetSelection(uint count, TS_SELECTION_ACP[] sel) { Sel = sel[0].end; }
    public void GetText(int s, int e, IntPtr plain, uint cchReq, out uint cchRet, IntPtr runs, uint runReq, out uint runRet, out int next) {
        int end = e == -1 ? Text.Length : Math.Min(e, Text.Length); int st = Math.Min(s, Text.Length);
        string chunk = Text.Substring(st, Math.Max(0, end - st)); if (chunk.Length > cchReq) chunk = chunk.Substring(0, (int)cchReq);
        if (plain != IntPtr.Zero) for (int i = 0; i < chunk.Length; i++) Marshal.WriteInt16(plain, i * 2, (short)chunk[i]);
        cchRet = (uint)chunk.Length; runRet = 0; next = st + chunk.Length;
    }
    void Apply(int s, int e, string t, out TS_TEXTCHANGE tc) {
        if (e < 0 || e > Text.Length) e = Text.Length; if (s > e) s = e;
        Text = Text.Substring(0, s) + t + Text.Substring(e); tc.start = s; tc.oldEnd = e; tc.newEnd = s + t.Length; Sel = s + t.Length; Trace.Add(Text);
    }
    public void SetText(uint f, int s, int e, string t, uint cch, out TS_TEXTCHANGE tc) { Apply(s, e, t ?? "", out tc); }
    public void GetFormattedText(int s, int e, out object o) { throw new COMException("E_NOTIMPL", unchecked((int)0x80004001)); }
    public void GetEmbedded(int p, ref Guid g, ref Guid r, out object o) { throw new COMException("E_NOTIMPL", unchecked((int)0x80004001)); }
    public void QueryInsertEmbedded(ref Guid g, IntPtr f, out bool ok) { ok = false; }
    public void InsertEmbedded(uint f, int s, int e, object o, out TS_TEXTCHANGE tc) { throw new COMException("E_NOTIMPL", unchecked((int)0x80004001)); }
    public void InsertTextAtSelection(uint f, string t, uint cch, out int rs, out int re, out TS_TEXTCHANGE tc) { rs = Sel; Apply(Sel, Sel, t ?? "", out tc); re = Sel; }
    public void InsertEmbeddedAtSelection(uint f, object o, out int rs, out int re, out TS_TEXTCHANGE tc) { throw new COMException("E_NOTIMPL", unchecked((int)0x80004001)); }
    public void RequestSupportedAttrs(uint f, uint n, IntPtr a) { }
    public void RequestAttrsAtPosition(int p, uint n, IntPtr a, uint f) { }
    public void RequestAttrsTransitioningAtPosition(int p, uint n, IntPtr a, uint f) { }
    public void FindNextAttrTransition(int s, int h, uint n, IntPtr a, uint f, out int next, out bool found, out int off) { next = 0; found = false; off = 0; }
    public void RetrieveRequestedAttrs(uint n, IntPtr a, out uint fetched) { fetched = 0; }
    public void GetEndACP(out int acp) { acp = Text.Length; }
    public void GetActiveView(out uint view) { view = 1; }
    public void GetACPFromPoint(uint v, ref POINT pt, uint f, out int acp) { throw new COMException("E_NOTIMPL", unchecked((int)0x80004001)); }
    public void GetTextExt(uint v, int s, int e, out RECT r, out bool clipped) { r.l = 100; r.t = 100; r.r = 200; r.b = 130; clipped = false; }
    public void GetScreenExt(uint v, out RECT r) { r.l = 0; r.t = 0; r.r = 800; r.b = 600; }
    public void GetWnd(uint v, out IntPtr h) { h = Hwnd; }
}

static class Dbg {
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Veh(IntPtr ep);
    [DllImport("kernel32.dll")] static extern IntPtr AddVectoredExceptionHandler(uint first, Veh h);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("ntdll.dll")] static extern int NtQueryInformationProcess(IntPtr p, int cls, IntPtr buf, int len, out int ret);
    static Veh keep;
    public static void Install() {
        // make IsDebuggerPresent() true (PEB.BeingDebugged) and capture OutputDebugString via first-chance exceptions
        IntPtr buf = Marshal.AllocHGlobal(48); int ret; NtQueryInformationProcess(GetCurrentProcess(), 0, buf, 48, out ret);
        IntPtr peb = Marshal.ReadIntPtr(buf, 8); Marshal.WriteByte(peb, 2, 1);
        keep = delegate(IntPtr ep) {
            IntPtr rec = Marshal.ReadIntPtr(ep, 0); uint code = (uint)Marshal.ReadInt32(rec, 0);
            if (code == 0x4001000A || code == 0x40010006) {
                int n = Marshal.ReadInt32(rec, 24); IntPtr p = Marshal.ReadIntPtr(rec, 32 + 8);
                string t = code == 0x4001000A ? Marshal.PtrToStringUni(p) : Marshal.PtrToStringAnsi(p);
                Console.WriteLine("[TIP] " + (t ?? "").TrimEnd());
                return -1;
            }
            return 0;
        };
        AddVectoredExceptionHandler(1, keep);
    }
}

static class Program {
    [DllImport("msctf.dll")] static extern int TF_CreateThreadMgr(out ITfThreadMgr tm);
    [DllImport("ole32.dll")] static extern int CoInitializeEx(IntPtr r, uint f);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr CreateWindowEx(uint ex, string cls, string name, uint style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr inst, IntPtr p);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, UIntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool PeekMessage(out MSG m, IntPtr h, uint a, uint b, uint rm);
    [DllImport("user32.dll")] static extern bool TranslateMessage(ref MSG m);
    [DllImport("user32.dll")] static extern IntPtr DispatchMessage(ref MSG m);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint c, uint t);
    [DllImport("user32.dll")] static extern short VkKeyScan(char c);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr SetFocus(IntPtr h);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();

    static void Pump(int ms) {
        DateTime end = DateTime.Now.AddMilliseconds(ms); MSG m;
        while (DateTime.Now < end) { while (PeekMessage(out m, IntPtr.Zero, 0, 0, 1)) { TranslateMessage(ref m); DispatchMessage(ref m); } Thread.Sleep(5); }
    }

    [STAThread]
    static int Main(string[] args) {
        Console.OutputEncoding = new UTF8Encoding(false);
        string keys = args.Length > 0 ? args[0] : "hk4g4bp4j4";
        string clsidText = args.Length > 1 ? args[1] : "{13F2EF08-575C-4D8C-88E0-F67BB8052B84}";
        string profText = args.Length > 2 ? args[2] : "{CE45F71D-CE79-41D1-967D-640B65A380E3}";
        if (args.Length > 3 && args[3] == "dbg") Dbg.Install();
        CoInitializeEx(IntPtr.Zero, 2);
        ITfThreadMgr tm; Console.WriteLine("TF_CreateThreadMgr " + TF_CreateThreadMgr(out tm).ToString("x"));
        uint tid; tm.Activate(out tid);
        IntPtr hwnd = CreateWindowEx(0, "EDIT", "", 0x10CF0004, 100, 100, 600, 200, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
        ShowWindow(hwnd, 5);
        keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero);   // Alt tap: allows SetForegroundWindow
        SetForegroundWindow(hwnd); SetFocus(hwnd); Console.WriteLine("foreground window is ours: " + (GetForegroundWindow() == hwnd));
        PostMessage(hwnd, 0x0050, UIntPtr.Zero, (IntPtr)0x04040404); Pump(500);
        Store store = new Store(); store.Hwnd = hwnd;
        ITfDocumentMgr dm; tm.CreateDocumentMgr(out dm);
        ITfContext ctx; uint ec; dm.CreateContext(tid, 0, store, out ctx, out ec); dm.Push(ctx); tm.SetFocus(dm);
        ITfInputProcessorProfileMgr pm = (ITfInputProcessorProfileMgr)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("33C53A50-F456-4884-B049-85FD643ECFED")));
        Guid clsid = new Guid(clsidText), prof = new Guid(profText);
        pm.ActivateProfile(1, 0x0404, ref clsid, ref prof, IntPtr.Zero, 0x10000001);
        Pump(5000);
        bool tf; tm.IsThreadFocus(out tf); Console.WriteLine("IsThreadFocus " + tf);
        try {
            IntPtr cmp; tm.GetGlobalCompartment(out cmp);
            ITfCompartmentMgr cm = (ITfCompartmentMgr)Marshal.GetObjectForIUnknown(cmp);
            Guid oc = new Guid("58273AAD-01BB-4164-95DF-FE6F8A5C9F26"); ITfCompartment c; cm.GetCompartment(ref oc, out c);
            object v; try { c.GetValue(out v); } catch (Exception) { v = null; }
            Console.WriteLine("keyboard open/close compartment before: " + (v == null ? "(unset)" : v.ToString()));
            object one = 1; c.SetValue(tid, ref one); Pump(500);
            c.GetValue(out v); Console.WriteLine("after set: " + v);
        } catch (Exception ex) { Console.WriteLine("compartment error: " + ex.Message); }
        try {   // the TIP ignores keys when the context's EMPTYCONTEXT compartment is 1: mark ours as not empty
            ITfCompartmentMgr ccm = (ITfCompartmentMgr)ctx;
            Guid ec2 = new Guid("D7487DBF-804E-41C5-894D-AD96FD4EEA13"); ITfCompartment cc; ccm.GetCompartment(ref ec2, out cc);
            object v0; try { cc.GetValue(out v0); } catch (Exception) { v0 = null; }
            Console.WriteLine("EMPTYCONTEXT before: " + (v0 == null ? "(unset)" : v0.ToString()));
            object zero = 0; cc.SetValue(tid, ref zero);
            Guid kd = new Guid("71A5B253-1951-466B-9FBC-9C8EB7266C1D"); ITfCompartment kc; ccm.GetCompartment(ref kd, out kc);
            kc.SetValue(tid, ref zero);
        } catch (Exception ex) { Console.WriteLine("context compartment error: " + ex.Message); }
        ITfKeystrokeMgr ksm = (ITfKeystrokeMgr)tm; Guid fg; ksm.GetForeground(out fg);
        Console.WriteLine("foreground TIP " + fg);
        foreach (char c in keys) {
            uint vk = c == '_' ? 0x20u : c == '~' ? 0x09u : c == '!' ? 0x0Du : (uint)(VkKeyScan(c) & 0xff); uint scan = MapVirtualKey(vk, 0);
            IntPtr lp = (IntPtr)(1 | (scan << 16)); bool eaten;
            ksm.KeyDown((UIntPtr)vk, lp, out eaten);
            bool e2; ksm.KeyUp((UIntPtr)vk, (IntPtr)(1 | (scan << 16) | (1 << 30) | unchecked((int)0x80000000)), out e2);
            Pump(400);
            Console.WriteLine("key '" + c + "' eaten=" + eaten + " text=" + store.Text);
        }
        Console.WriteLine("FINAL " + store.Text);
        return 0;
    }
}
