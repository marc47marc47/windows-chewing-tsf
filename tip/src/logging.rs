// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Kan-Ru Chen

use logforth::{Append, Diagnostic, Error, Layout, layout::PlainTextLayout, record::Record};
use windows::Win32::System::Diagnostics::Debug::{IsDebuggerPresent, OutputDebugStringW};
use windows_core::HSTRING;

#[derive(Debug)]
pub(crate) struct WinDbg {
    layout: Box<dyn Layout>,
}

impl Default for WinDbg {
    fn default() -> Self {
        Self {
            layout: Box::new(PlainTextLayout::default()),
        }
    }
}

impl Append for WinDbg {
    fn append(&self, record: &Record, diags: &[Box<dyn Diagnostic>]) -> Result<(), Error> {
        if is_debugger_present() {
            let mut bytes = self.layout.format(record, diags)?;
            bytes.push(b'\n');
            let text = String::from_utf8_lossy(&bytes);
            output_debug_string(&text);
        }
        Ok(())
    }
    fn flush(&self) -> Result<(), Error> {
        Ok(())
    }
}

pub(crate) fn output_debug_string(text: &str) {
    unsafe {
        OutputDebugStringW(&HSTRING::from(text));
    }
}

pub(crate) fn is_debugger_present() -> bool {
    unsafe { IsDebuggerPresent().as_bool() }
}

/// True when `HKCU\Software\ChewingTextService\DebugLog` is non-zero (opt-in file logging).
pub(crate) fn debug_log_enabled() -> bool {
    windows_registry::CURRENT_USER
        .open(r"Software\ChewingTextService")
        .and_then(|k| k.get_u32("DebugLog"))
        .map(|v| v != 0)
        .unwrap_or(false)
}

/// Appends every record to `%APPDATA%\Chewing\logs\chewing_tip_YYYYMMDD.log`, tagged with the host
/// process, so a problem seen in one application (a game, ...) can be diagnosed afterwards.
#[derive(Debug)]
pub(crate) struct FileLog {
    layout: Box<dyn Layout>,
    file: std::sync::Mutex<std::fs::File>,
    prefix: String,
}

impl FileLog {
    pub(crate) fn open() -> Option<FileLog> {
        use windows::Win32::System::{LibraryLoader::GetModuleFileNameW, SystemInformation::GetLocalTime};
        let dir = std::path::PathBuf::from(std::env::var_os("APPDATA")?)
            .join("Chewing")
            .join("logs");
        std::fs::create_dir_all(&dir).ok()?;
        let t = unsafe { GetLocalTime() };
        let path = dir.join(format!("chewing_tip_{:04}{:02}{:02}.log", t.wYear, t.wMonth, t.wDay));
        let file = std::fs::OpenOptions::new().create(true).append(true).open(path).ok()?;
        let mut buf = [0u16; 260];
        let len = unsafe { GetModuleFileNameW(None, &mut buf) as usize };
        let exe = String::from_utf16_lossy(&buf[..len.min(buf.len())]);
        let exe = exe.rsplit('\\').next().unwrap_or("?").to_string();
        Some(FileLog {
            layout: Box::new(PlainTextLayout::default()),
            file: std::sync::Mutex::new(file),
            prefix: format!("[{exe}:{}] ", std::process::id()),
        })
    }
}

impl Append for FileLog {
    fn append(&self, record: &Record, diags: &[Box<dyn Diagnostic>]) -> Result<(), Error> {
        use std::io::Write;
        if let Ok(bytes) = self.layout.format(record, diags)
            && let Ok(mut f) = self.file.lock()
        {
            let _ = f.write_all(self.prefix.as_bytes());
            let _ = f.write_all(&bytes);
            let _ = f.write_all(b"\n");
        }
        Ok(())
    }
    fn flush(&self) -> Result<(), Error> {
        Ok(())
    }
}
