// Types real key events (keybd_event) into a plain Win32 EDIT window so the system routes them through the
// user's default TSF input method (Chewing), then prints the EDIT text.
// Build (from this dir, MSYS_NO_PATHCONV=1): csc /nologo /platform:x64 /out:edittyper.exe EditTyper.cs
// Run: edittyper.exe KEYS   KEYS: letters/digits as-is, '_' Space, '~' Tab, '!' Enter, '<' Left
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;

[ComImport, Guid("71C6E74C-0F28-11D8-A82A-00065B84435C"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IProfileMgr {
    void ActivateProfile(uint type, ushort lang, ref Guid clsid, ref Guid profile, IntPtr hkl, uint flags);
}

class Dbg {
    [StructLayout(LayoutKind.Sequential)] struct PBI { public IntPtr exit, peb, aff, prio, pid, ppid; }
    [DllImport("ntdll")] static extern int NtQueryInformationProcess(IntPtr h, int cls, ref PBI pbi, int len, out int ret);
    [DllImport("kernel32")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32")] static extern IntPtr AddVectoredExceptionHandler(uint first, VehProc h);
    delegate int VehProc(IntPtr info);
    static VehProc keep;
    public static void Install() {
        keep = Handler; AddVectoredExceptionHandler(1, keep);
        PBI pbi = new PBI(); int ret; NtQueryInformationProcess(GetCurrentProcess(), 0, ref pbi, Marshal.SizeOf(pbi), out ret);
        Marshal.WriteByte(pbi.peb, 2, 1);   // PEB.BeingDebugged = 1 so the TIP emits its log through OutputDebugString
    }
    static int Handler(IntPtr info) {
        IntPtr rec = Marshal.ReadIntPtr(info);
        uint code = (uint)Marshal.ReadInt32(rec);
        if (code == 0x4001000A || code == 0x40010006) {   // DBG_PRINTEXCEPTION_WIDE_C / DBG_PRINTEXCEPTION_C
            IntPtr p = Marshal.ReadIntPtr(rec, 32 + 8);   // ExceptionInformation[1]
            try { Console.Write("[dbg] " + (code == 0x4001000A ? Marshal.PtrToStringUni(p) : Marshal.PtrToStringAnsi(p))); } catch (Exception) {}
            return -1;   // EXCEPTION_CONTINUE_EXECUTION
        }
        return 0;
    }
}

class EditTyper {
    [DllImport("user32")] static extern IntPtr CreateWindowEx(int ex, string cls, string name, uint style, int x, int y, int w, int h, IntPtr p, IntPtr m, IntPtr i, IntPtr l);
    [DllImport("user32")] static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32")] static extern IntPtr SetFocus(IntPtr h);
    [DllImport("user32")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32")] static extern short VkKeyScan(char c);
    [DllImport("user32")] static extern bool PeekMessage(out MSG m, IntPtr h, uint a, uint b, uint r);
    [DllImport("user32")] static extern bool TranslateMessage(ref MSG m);
    [DllImport("user32")] static extern IntPtr DispatchMessage(ref MSG m);
    [DllImport("user32", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32")] static extern bool DestroyWindow(IntPtr h);
    [DllImport("kernel32", CharSet=CharSet.Unicode)] static extern IntPtr GetModuleHandleW(string n);
    [DllImport("user32")] static extern short GetKeyState(int k);
    [DllImport("user32")] static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32")] static extern int ReleaseDC(IntPtr h, IntPtr dc);
    static void Backdrop(IntPtr hwnd, int w, int hgt) {   // colourful stripes so blur is visible
        IntPtr dc = GetDC(hwnd);
        using (Graphics g = Graphics.FromHdc(dc)) {
            int B = Environment.GetEnvironmentVariable("BLOCK") != null ? int.Parse(Environment.GetEnvironmentVariable("BLOCK")) : 6;
            for (int y = 0; y < hgt; y += B) {
                for (int x = 0; x < w; x += B) {
                    int v = ((x / B) * 37 + (y / B) * 91) % 255;
                    Color c = (((x / B) + (y / B)) % 3 == 0) ? Color.FromArgb(40, 120 + v / 3, 230) : (((x / B) % 2 == 0) ? Color.FromArgb(240, 170, 20 + v / 4) : Color.FromArgb(20, 60, 160 + v / 3));
                    using (var b = new SolidBrush(c)) g.FillRectangle(b, x, y, B, B);
                }
            }
        }
        ReleaseDC(hwnd, dc);
    }
    [DllImport("kernel32", CharSet=CharSet.Unicode)] static extern uint GetModuleFileNameW(IntPtr m, StringBuilder b, int n);
    static string ModPath(string name) { IntPtr m = GetModuleHandleW(name); if (m == IntPtr.Zero) return "(not loaded)"; var sb = new StringBuilder(520); GetModuleFileNameW(m, sb, 520); return sb.ToString(); }
    [DllImport("ole32")] static extern int CoInitializeEx(IntPtr r, uint f);
    [StructLayout(LayoutKind.Sequential)] struct MSG { public IntPtr hwnd; public uint message; public UIntPtr w; public IntPtr l; public uint time; public int x, y; }

    static void Pump(int ms) {
        DateTime end = DateTime.Now.AddMilliseconds(ms); MSG m;
        while (DateTime.Now < end) {
            while (PeekMessage(out m, IntPtr.Zero, 0, 0, 1)) { TranslateMessage(ref m); DispatchMessage(ref m); }
            System.Threading.Thread.Sleep(5);
        }
    }
    static void Tap(byte vk) {
        keybd_event(vk, 0, 0, UIntPtr.Zero); Pump(30); keybd_event(vk, 0, 2, UIntPtr.Zero);
    }
    static string Text(IntPtr h) { var sb = new StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }

    static int Main(string[] a) {
        Console.OutputEncoding = new UTF8Encoding(false);
        if (a.Length > 2 && a[2] == "dbg") Dbg.Install();
        CoInitializeEx(IntPtr.Zero, 2);
        bool capsWasOn = (GetKeyState(0x14) & 1) != 0;
        string shot = Environment.GetEnvironmentVariable("SHOT");
        IntPtr back = IntPtr.Zero;
        if (shot != null) { back = CreateWindowEx(0, "STATIC", "", 0x10000000, 60, 60, 760, 420, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero); ShowWindow(back, 5); Pump(300); Backdrop(back, 760, 420); }
        IntPtr h = CreateWindowEx(0, "EDIT", "", 0x10CF0004, 100, 100, 600, 120, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
        ShowWindow(h, 5);
        keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero);
        SetForegroundWindow(h); SetFocus(h); Pump(1500);
        if (a.Length > 1 && a[1] == "activate") {   // make Chewing the active profile of THIS process only
            var pm = (IProfileMgr)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("33C53A50-F456-4884-B049-85FD643ECFED")));
            Guid clsid = new Guid("13F2EF08-575C-4D8C-88E0-F67BB8052B84"), prof = new Guid("CE45F71D-CE79-41D1-967D-640B65A380E3");
            pm.ActivateProfile(1, 0x0404, ref clsid, ref prof, IntPtr.Zero, 0x10000001); Pump(2500);
        }
        // user config LockChineseOnCapsLock=1: Caps Lock ON = Chinese mode. The TIP switches mode when it SEES the
        // Caps Lock key, so press it after the TIP is active (and again at the end to restore the original state).
        if (!capsWasOn && Environment.GetEnvironmentVariable("EDITTYPER_NOCAPS") == null) { Tap(0x14); Pump(500); }
        Console.WriteLine("foreground is ours: " + (GetForegroundWindow() == h));
        // user config LockChineseOnCapsLock=1: Caps Lock ON = Chinese mode. Turn it on for the test, restore afterwards.
        foreach (char c in a[0]) {
            byte vk = c == '_' ? (byte)0x20 : c == '~' ? (byte)0x09 : c == '!' ? (byte)0x0D : c == '<' ? (byte)0x25 : (byte)(VkKeyScan(c) & 0xff);
            Tap(vk); Pump(250);
        }
        if (!capsWasOn && Environment.GetEnvironmentVariable("EDITTYPER_NOCAPS") == null) { Tap(0x14); Pump(200); }
        Pump(500);
        if (shot != null) {
            if (back != IntPtr.Zero) { Backdrop(back, 760, 420); }
            Pump(1200);
            using (Bitmap bmp = new Bitmap(900, 560)) {
                using (Graphics g = Graphics.FromImage(bmp)) g.CopyFromScreen(40, 40, 0, 0, bmp.Size);
                bmp.Save(shot, ImageFormat.Png);
            }
        }
        Console.WriteLine("stub loaded=" + (GetModuleHandleW("chewing_tip.dll") != IntPtr.Zero) + " impl loaded=" + (GetModuleHandleW("chewing_tip_impl.dll") != IntPtr.Zero) + " old-flat loaded=" + (GetModuleHandleW("chewing_tip_x64_26_11_1125.dll") != IntPtr.Zero));
        Console.WriteLine("impl path: " + ModPath("chewing_tip_impl.dll"));
        Console.WriteLine("TEXT=[" + Text(h).Replace("\r", "\\r").Replace("\n", "\\n") + "]");
        DestroyWindow(h);
        return 0;
    }
}
