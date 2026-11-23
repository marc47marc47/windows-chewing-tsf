using System; using System.Runtime.InteropServices;
class P {
  [DllImport("kernel32", CharSet=CharSet.Unicode)] static extern IntPtr LoadLibraryW(string p);
  [DllImport("kernel32")] static extern IntPtr GetProcAddress(IntPtr m, string n);
  [DllImport("kernel32")] static extern uint GetModuleFileNameW(IntPtr m, System.Text.StringBuilder b, int n);
  [DllImport("kernel32")] static extern IntPtr GetModuleHandleW(string n);
  delegate int GetCls(ref Guid clsid, ref Guid iid, out IntPtr obj);
  static void Main(string[] a) {
    IntPtr m = LoadLibraryW(a[0]); Console.WriteLine("stub loaded: " + (m != IntPtr.Zero));
    var f = (GetCls)Marshal.GetDelegateForFunctionPointer(GetProcAddress(m, "DllGetClassObject"), typeof(GetCls));
    Guid clsid = new Guid("13F2EF08-575C-4D8C-88E0-F67BB8052B84"), iid = new Guid("00000001-0000-0000-C000-000000000046"); IntPtr o;
    int hr = f(ref clsid, ref iid, out o); Console.WriteLine("DllGetClassObject hr=0x" + hr.ToString("x") + " obj=" + (o != IntPtr.Zero));
    IntPtr impl = GetModuleHandleW("chewing_tip_impl.dll"); var sb = new System.Text.StringBuilder(500);
    GetModuleFileNameW(impl, sb, 500); Console.WriteLine("impl loaded from: " + sb);
  }
}
