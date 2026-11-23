// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Kan-Ru Chen

use std::{
    ffi::{c_int, c_void},
    sync::atomic::{AtomicUsize, Ordering},
};

use logforth::record::{Level, LevelFilter};
use windows::Win32::System::{
    Com::{CoLockObjectExternal, IClassFactory, IClassFactory_Impl},
    Console::{ATTACH_PARENT_PROCESS, AttachConsole},
};
use windows::Win32::{Foundation::TRUE, System::SystemServices::DLL_PROCESS_ATTACH};
use windows::core::{
    BOOL, ComObjectInner, ComObjectInterface, GUID, HRESULT, IUnknown, Interface, Ref, Result,
    implement,
};

use crate::{
    logging::{self, WinDbg},
    text_service::TextService,
};

pub(crate) static G_HINSTANCE: AtomicUsize = AtomicUsize::new(0);

#[unsafe(no_mangle)]
extern "system" fn DllMain(
    hmodule: *mut c_void,
    ul_reason_for_call: u32,
    _reserved: *const c_void,
) -> c_int {
    if let DLL_PROCESS_ATTACH = ul_reason_for_call {
        let g_hinstance = G_HINSTANCE.load(Ordering::Relaxed);
        if g_hinstance == 0 {
            G_HINSTANCE.store(hmodule as usize, Ordering::Relaxed);
            let debugger = logging::is_debugger_present();
            let file_log = if logging::debug_log_enabled() { logging::FileLog::open() } else { None };
            if debugger || file_log.is_some() {
                if debugger {
                    unsafe {
                        let _ = AttachConsole(ATTACH_PARENT_PROCESS);
                    }
                }
                let verbose = cfg!(debug_assertions) || file_log.is_some();
                logforth::starter_log::builder()
                    .dispatch(|d| {
                        let mut d = d
                            .filter(if verbose {
                                LevelFilter::MoreSevereEqual(Level::Debug)
                            } else {
                                LevelFilter::MoreSevereEqual(Level::Info)
                            })
                            .append(WinDbg::default());
                        if debugger {
                            d = d.append(logforth::append::Stderr::default());
                        }
                        if let Some(f) = file_log {
                            d = d.append(f);
                        }
                        d
                    })
                    .apply();
            }
            log::info!("chewing_tip.dll loaded");
        }
    }
    TRUE.0
}

#[unsafe(no_mangle)]
extern "system" fn DllGetClassObject(
    _rclsid: *const c_void,
    riid: *const GUID,
    ppv_obj: *mut *mut c_void,
) -> HRESULT {
    let factory: IUnknown = CClassFactory::new().into_object().into_interface();
    unsafe { factory.query(riid, ppv_obj) }
}

#[implement(IClassFactory)]
struct CClassFactory;

impl CClassFactory {
    fn new() -> CClassFactory {
        CClassFactory
    }
}

impl IClassFactory_Impl for CClassFactory_Impl {
    fn CreateInstance(
        &self,
        _punkouter: Ref<'_, IUnknown>,
        riid: *const GUID,
        ppvobject: *mut *mut c_void,
    ) -> Result<()> {
        let text_service: IUnknown = TextService::new().into_object().into_interface();
        unsafe {
            text_service.query(riid, ppvobject).ok()?;
        }
        Ok(())
    }

    fn LockServer(&self, flock: BOOL) -> Result<()> {
        unsafe { CoLockObjectExternal(self.as_interface_ref(), flock.as_bool(), true) }
    }
}
