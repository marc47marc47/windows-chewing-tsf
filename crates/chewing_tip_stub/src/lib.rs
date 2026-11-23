// SPDX-License-Identifier: GPL-3.0-or-later
//! Stable entry point registered as the TSF/COM server.
//!
//! Layout (Chrome style):
//! ```text
//! ChewingTextService\chewing_tip.dll        <- this stub, registered once, almost never changes
//! ChewingTextService\26.11.1124\chewing_tip_impl.dll
//! ChewingTextService\26.11.1125\chewing_tip_impl.dll   <- newest, picked when a process loads the IME
//! ```
//! A process keeps the version it first loaded; new processes pick the newest one. Because a new
//! version never overwrites a loaded file, upgrading needs no restart.

use std::ffi::c_void;
use std::os::windows::ffi::{OsStrExt, OsStringExt};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

/// File name of the real implementation inside each version directory.
pub const IMPL_NAME: &str = "chewing_tip_impl.dll";

type Hresult = i32;
const S_OK: Hresult = 0;
const S_FALSE: Hresult = 1;
const CLASS_E_CLASSNOTAVAILABLE: Hresult = 0x8004_0111_u32 as i32;

type GetClassObjectFn = unsafe extern "system" fn(*const c_void, *const c_void, *mut *mut c_void) -> Hresult;

struct Loaded {
    get_class_object: GetClassObjectFn,
}

unsafe extern "system" {
    fn LoadLibraryExW(name: *const u16, file: *mut c_void, flags: u32) -> *mut c_void;
    fn GetProcAddress(module: *mut c_void, name: *const u8) -> *mut c_void;
    fn GetModuleHandleExW(flags: u32, addr: *const c_void, out: *mut *mut c_void) -> i32;
    fn GetModuleFileNameW(module: *mut c_void, buf: *mut u16, len: u32) -> u32;
}

const LOAD_WITH_ALTERED_SEARCH_PATH: u32 = 0x8;
const GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS: u32 = 0x4;
const GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT: u32 = 0x2;

/// "26.11.1125" -> [26, 11, 1125]
pub fn parse_version(name: &str) -> Option<Vec<u64>> {
    let parts: Option<Vec<u64>> = name.split('.').map(|p| p.parse().ok()).collect();
    parts.filter(|p| p.len() >= 2)
}

/// Candidate implementation DLLs under `root`, newest version first.
pub fn candidates(root: &Path) -> Vec<PathBuf> {
    let mut found: Vec<_> = std::fs::read_dir(root)
        .into_iter()
        .flatten()
        .flatten()
        .filter_map(|e| {
            let v = parse_version(&e.file_name().to_string_lossy())?;
            let dll = e.path().join(IMPL_NAME);
            dll.is_file().then_some((v, dll))
        })
        .collect();
    found.sort_by(|a, b| b.0.cmp(&a.0));
    found.into_iter().map(|(_, p)| p).collect()
}

fn stub_dir() -> Option<PathBuf> {
    unsafe {
        let mut module = std::ptr::null_mut();
        let anchor = DllGetClassObject as *const c_void;
        if GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            anchor,
            &mut module,
        ) == 0
        {
            return None;
        }
        let mut buf = [0u16; 1024];
        let len = GetModuleFileNameW(module, buf.as_mut_ptr(), buf.len() as u32) as usize;
        if len == 0 || len >= buf.len() {
            return None;
        }
        PathBuf::from(std::ffi::OsString::from_wide(&buf[..len])).parent().map(Path::to_path_buf)
    }
}

fn load_from(root: &Path) -> Option<Loaded> {
    for dll in candidates(root) {
        let wide: Vec<u16> = dll.as_os_str().encode_wide().chain(Some(0)).collect();
        let module = unsafe { LoadLibraryExW(wide.as_ptr(), std::ptr::null_mut(), LOAD_WITH_ALTERED_SEARCH_PATH) };
        if module.is_null() {
            continue; // broken or half-deleted version: try the next older one
        }
        let get = unsafe { GetProcAddress(module, c"DllGetClassObject".as_ptr().cast()) };
        if get.is_null() {
            continue;
        }
        return Some(Loaded {
            get_class_object: unsafe { std::mem::transmute::<*mut c_void, GetClassObjectFn>(get) },
        });
    }
    None
}

fn loaded() -> Option<&'static Loaded> {
    static LOADED: OnceLock<Option<Loaded>> = OnceLock::new();
    LOADED.get_or_init(|| stub_dir().and_then(|d| load_from(&d))).as_ref()
}

#[unsafe(no_mangle)]
pub unsafe extern "system" fn DllMain(_module: *mut c_void, _reason: u32, _reserved: *mut c_void) -> i32 {
    1
}

#[unsafe(no_mangle)]
pub unsafe extern "system" fn DllGetClassObject(clsid: *const c_void, iid: *const c_void, out: *mut *mut c_void) -> Hresult {
    match loaded() {
        Some(l) => unsafe { (l.get_class_object)(clsid, iid, out) },
        None => CLASS_E_CLASSNOTAVAILABLE,
    }
}

#[unsafe(no_mangle)]
pub unsafe extern "system" fn DllCanUnloadNow() -> Hresult {
    match loaded() {
        // the implementation DLL is never unloaded (it is pinned in memory), so never allow the stub out either
        Some(_) => S_FALSE,
        None => S_OK,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn picks_newest_version_with_dll_first() {
        let root = std::env::temp_dir().join(format!("stub_test_{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        for v in ["26.11.999", "26.11.1124", "26.11.1125", "26.11.1126"] {
            fs::create_dir_all(root.join(v)).unwrap();
        }
        for v in ["26.11.999", "26.11.1124", "26.11.1125"] {
            fs::write(root.join(v).join(IMPL_NAME), b"x").unwrap(); // 1126 has no DLL (half-installed)
        }
        fs::create_dir_all(root.join("Dictionary")).unwrap();
        let names: Vec<_> = candidates(&root)
            .iter()
            .map(|p| p.parent().unwrap().file_name().unwrap().to_string_lossy().to_string())
            .collect();
        assert_eq!(names, vec!["26.11.1125", "26.11.1124", "26.11.999"]);
        let _ = fs::remove_dir_all(&root);
    }
}
