// SPDX-License-Identifier: GPL-3.0-or-later
//! System fonts for the egui renderer, memory-mapped instead of read: a CJK font is 10-20 MB and this
//! code lives in every program that uses the IME, so the pages must be shared, not copied.

use std::ffi::c_void;
use std::path::{Path, PathBuf};
use std::sync::{Arc, OnceLock};

use chewing_ui::candidate::FontBlob;
use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::Storage::FileSystem::{
    CreateFileW, FILE_ATTRIBUTE_NORMAL, FILE_GENERIC_READ, FILE_SHARE_READ, GetFileSizeEx,
    OPEN_EXISTING,
};
use windows::Win32::System::Memory::{
    CreateFileMappingW, FILE_MAP_READ, MapViewOfFile, PAGE_READONLY, UnmapViewOfFile,
};
use windows::core::HSTRING;

/// A read-only memory mapping of a whole file.
struct MappedFile {
    view: *const u8,
    len: usize,
}

// The mapping is read-only and never modified, so sharing it between threads is fine.
unsafe impl Send for MappedFile {}
unsafe impl Sync for MappedFile {}

impl MappedFile {
    fn open(path: &Path) -> Option<MappedFile> {
        unsafe {
            let file = CreateFileW(
                &HSTRING::from(path.as_os_str()),
                FILE_GENERIC_READ.0,
                FILE_SHARE_READ,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None,
            )
            .ok()?;
            let result = Self::map(file);
            let _ = CloseHandle(file); // the view keeps the mapping alive
            result
        }
    }

    unsafe fn map(file: HANDLE) -> Option<MappedFile> {
        unsafe {
            let mut size = 0i64;
            GetFileSizeEx(file, &mut size).ok()?;
            if size <= 0 {
                return None;
            }
            let mapping = CreateFileMappingW(file, None, PAGE_READONLY, 0, 0, None).ok()?;
            let view = MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0);
            let _ = CloseHandle(mapping);
            if view.Value.is_null() {
                return None;
            }
            Some(MappedFile {
                view: view.Value as *const u8,
                len: size as usize,
            })
        }
    }
}

impl AsRef<[u8]> for MappedFile {
    fn as_ref(&self) -> &[u8] {
        unsafe { std::slice::from_raw_parts(self.view, self.len) }
    }
}

impl Drop for MappedFile {
    fn drop(&mut self) {
        unsafe {
            let _ = UnmapViewOfFile(windows::Win32::System::Memory::MEMORY_MAPPED_VIEW_ADDRESS {
                Value: self.view as *mut c_void,
            });
        }
    }
}

/// Preferred Traditional-Chinese capable fonts, open-source first.
const CJK_FONTS: &[&str] = &["NotoSansTC-VF.ttf", "msjh.ttc", "mingliu.ttc", "kaiu.ttf"];

fn fonts_dir() -> PathBuf {
    let root = std::env::var_os("SystemRoot").unwrap_or_else(|| r"C:\Windows".into());
    PathBuf::from(root).join("Fonts")
}

/// The fonts handed to the renderer; mapped once per process.
pub(crate) fn system_fonts() -> Vec<FontBlob> {
    static FONTS: OnceLock<Vec<FontBlob>> = OnceLock::new();
    FONTS
        .get_or_init(|| {
            CJK_FONTS
                .iter()
                .find_map(|name| MappedFile::open(&fonts_dir().join(name)))
                .map(|m| vec![Arc::new(m) as FontBlob])
                .unwrap_or_default()
        })
        .clone()
}
