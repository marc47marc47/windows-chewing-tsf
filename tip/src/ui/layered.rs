// SPDX-License-Identifier: GPL-3.0-or-later
//! Present a premultiplied-alpha BGRA pixel buffer through a layered window (`UpdateLayeredWindow`).
//! The only graphics API needed: plain GDI, no Direct2D / Direct3D / DirectComposition.

use windows::Win32::Foundation::{COLORREF, HWND, POINT, SIZE};
use windows::Win32::Graphics::Gdi::{
    AC_SRC_ALPHA, AC_SRC_OVER, BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION,
    CreateCompatibleDC, CreateDIBSection, DIB_RGB_COLORS, DeleteDC, DeleteObject, GetDC, HGDIOBJ,
    ReleaseDC, SelectObject,
};
use windows::Win32::UI::WindowsAndMessaging::{ULW_ALPHA, UpdateLayeredWindow};

/// Show `pixels` (`width * height * 4` bytes, B G R A premultiplied, top-down) with its top-left corner
/// at screen position (`x`, `y`). Returns false on failure.
pub(crate) fn present(hwnd: HWND, pixels: &[u8], width: usize, height: usize, x: i32, y: i32) -> bool {
    if width == 0 || height == 0 || pixels.len() < width * height * 4 {
        return false;
    }
    unsafe {
        let screen = GetDC(None);
        let mem = CreateCompatibleDC(Some(screen));
        let info = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: width as i32,
                biHeight: -(height as i32), // top-down
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };
        let mut bits = std::ptr::null_mut();
        let ok = match CreateDIBSection(Some(mem), &info, DIB_RGB_COLORS, &mut bits, None, 0) {
            Ok(dib) if !bits.is_null() => {
                std::ptr::copy_nonoverlapping(pixels.as_ptr(), bits as *mut u8, width * height * 4);
                let old = SelectObject(mem, HGDIOBJ(dib.0));
                let blend = BLENDFUNCTION {
                    BlendOp: AC_SRC_OVER as u8,
                    BlendFlags: 0,
                    SourceConstantAlpha: 255,
                    AlphaFormat: AC_SRC_ALPHA as u8,
                };
                let ok = UpdateLayeredWindow(
                    hwnd,
                    Some(screen),
                    Some(&POINT { x, y }),
                    Some(&SIZE { cx: width as i32, cy: height as i32 }),
                    Some(mem),
                    Some(&POINT { x: 0, y: 0 }),
                    COLORREF(0),
                    Some(&blend),
                    ULW_ALPHA,
                )
                .is_ok();
                SelectObject(mem, old);
                let _ = DeleteObject(HGDIOBJ(dib.0));
                ok
            }
            _ => false,
        };
        let _ = DeleteDC(mem);
        ReleaseDC(None, screen);
        ok
    }
}
