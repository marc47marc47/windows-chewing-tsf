// SPDX-License-Identifier: GPL-3.0-or-later
//! Self-rendered frosted glass for popup windows.
//!
//! DWM backdrops (system acrylic, accent blur) do not work for a window that never has focus and is
//! drawn with DirectComposition, so the effect is produced here: the screen area behind the window is
//! captured (the window itself is excluded from capture), blurred on the CPU, tinted, and drawn as the
//! panel background. It needs no particular Windows version and does not depend on window activation.
//!
//! Enabled with the registry value `CandidateAcrylic` = 1 (default 0 = opaque panel);
//! `CandidateAcrylicTint` (0-100) is the opacity of the colour laid over the blurred picture.

use windows::Win32::Foundation::{HWND, RECT};
use windows::Win32::Graphics::Gdi::{
    BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BitBlt, CAPTUREBLT, CreateCompatibleDC, CreateDIBSection,
    DIB_RGB_COLORS, DeleteDC, DeleteObject, GetDC, HGDIOBJ, ReleaseDC, SRCCOPY, SelectObject,
};
use windows::Win32::UI::WindowsAndMessaging::{
    GetWindowRect, SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE,
};

/// Blur radius in physical pixels (one box-blur pass each of three gives a close Gaussian).
pub(crate) const BLUR_RADIUS: usize = 14;

/// Keep the window itself out of screen captures so we can read what is *behind* it.
pub(crate) fn exclude_from_capture(hwnd: HWND) {
    let _ = unsafe { SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE) };
}

/// Capture the screen rectangle behind the window as top-down BGRA (alpha = 255).
/// Returns (pixels, width, height) or None when the capture fails.
pub(crate) fn capture_behind(hwnd: HWND) -> Option<(Vec<u8>, usize, usize)> {
    unsafe {
        let mut rect = RECT::default();
        GetWindowRect(hwnd, &mut rect).ok()?;
        let (w, h) = ((rect.right - rect.left) as usize, (rect.bottom - rect.top) as usize);
        if w == 0 || h == 0 {
            return None;
        }
        let screen = GetDC(None);
        if screen.is_invalid() {
            return None;
        }
        let mem = CreateCompatibleDC(Some(screen));
        let info = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: w as i32,
                biHeight: -(h as i32), // top-down
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };
        let mut bits = std::ptr::null_mut();
        let dib = CreateDIBSection(Some(mem), &info, DIB_RGB_COLORS, &mut bits, None, 0);
        let result = match dib {
            Ok(dib) if !bits.is_null() => {
                let old = SelectObject(mem, HGDIOBJ(dib.0));
                let ok = BitBlt(mem, 0, 0, w as i32, h as i32, Some(screen), rect.left, rect.top, SRCCOPY | CAPTUREBLT)
                    .is_ok();
                let out = ok.then(|| {
                    let mut px = std::slice::from_raw_parts(bits as *const u8, w * h * 4).to_vec();
                    for a in px.iter_mut().skip(3).step_by(4) {
                        *a = 255;
                    }
                    (px, w, h)
                });
                SelectObject(mem, old);
                let _ = DeleteObject(HGDIOBJ(dib.0));
                out
            }
            _ => None,
        };
        let _ = DeleteDC(mem);
        ReleaseDC(None, screen);
        result
    }
}

/// Separable moving-average blur over BGRA pixels (alpha untouched), edges clamped.
pub(crate) fn box_blur(px: &mut [u8], w: usize, h: usize, radius: usize, passes: usize) {
    if radius == 0 || w == 0 || h == 0 {
        return;
    }
    let mut tmp = vec![0u8; px.len()];
    for _ in 0..passes {
        blur_axis(px, &mut tmp, w, h, radius, true);
        blur_axis(&tmp, px, w, h, radius, false);
    }
}

fn blur_axis(src: &[u8], dst: &mut [u8], w: usize, h: usize, r: usize, horizontal: bool) {
    let (len, lines, stride_i, stride_l) = if horizontal { (w, h, 4, w * 4) } else { (h, w, w * 4, 4) };
    let window = (2 * r + 1) as u32;
    for line in 0..lines {
        let base = line * stride_l;
        for c in 0..3 {
            let at = |i: isize| -> u32 {
                let i = i.clamp(0, len as isize - 1) as usize;
                src[base + i * stride_i + c] as u32
            };
            let mut sum: u32 = (-(r as isize)..=(r as isize)).map(at).sum();
            for i in 0..len {
                dst[base + i * stride_i + c] = (sum / window) as u8;
                sum = sum + at(i as isize + r as isize + 1) - at(i as isize - r as isize);
            }
        }
        for i in 0..len {
            dst[base + i * stride_i + 3] = src[base + i * stride_i + 3];
        }
    }
}

/// Encode top-down BGRA pixels as a 32-bit BMP file (used to dump the effect for inspection).
pub(crate) fn encode_bmp(px: &[u8], w: usize, h: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(54 + px.len());
    let size = (54 + px.len()) as u32;
    out.extend_from_slice(b"BM");
    out.extend_from_slice(&size.to_le_bytes());
    out.extend_from_slice(&[0; 4]);
    out.extend_from_slice(&54u32.to_le_bytes());
    out.extend_from_slice(&40u32.to_le_bytes());
    out.extend_from_slice(&(w as i32).to_le_bytes());
    out.extend_from_slice(&(-(h as i32)).to_le_bytes()); // negative height = top-down
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&32u16.to_le_bytes());
    out.extend_from_slice(&[0; 24]);
    out.extend_from_slice(px);
    out
}

/// Lay a colour (straight RGB 0..=1) over the picture with the given opacity (0..=1).
pub(crate) fn tint(px: &mut [u8], r: f32, g: f32, b: f32, alpha: f32) {
    let a = alpha.clamp(0.0, 1.0);
    let c = [b, g, r].map(|v| v.clamp(0.0, 1.0) * 255.0);
    for p in px.chunks_exact_mut(4) {
        for i in 0..3 {
            p[i] = (p[i] as f32 * (1.0 - a) + c[i] * a).round() as u8;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blur_averages_a_hard_edge() {
        // 8x1 image: left half black, right half white
        let mut px = vec![0u8; 8 * 4];
        for x in 4..8 {
            px[x * 4..x * 4 + 3].copy_from_slice(&[255, 255, 255]);
        }
        for a in px.iter_mut().skip(3).step_by(4) {
            *a = 255;
        }
        box_blur(&mut px, 8, 1, 1, 1);
        // edge pixels become intermediate greys, the far ends stay put
        assert_eq!(px[0], 0);
        assert!(px[3 * 4] > 0 && px[3 * 4] < 255);
        assert!(px[4 * 4] > 0 && px[4 * 4] < 255);
        assert_eq!(px[7 * 4], 255);
        assert_eq!(px[3], 255); // alpha untouched
    }

    #[test]
    fn blur_keeps_a_flat_colour() {
        let mut px = [40u8, 80, 120, 255].repeat(6 * 5);
        box_blur(&mut px, 6, 5, 3, 3);
        assert!(px.chunks(4).all(|p| p == [40, 80, 120, 255]));
    }

    #[test]
    fn tint_mixes_towards_colour() {
        let mut px = vec![0u8, 0, 0, 255];
        tint(&mut px, 1.0, 1.0, 1.0, 0.5);
        assert_eq!(px, vec![128, 128, 128, 255]);
        tint(&mut px, 0.0, 0.0, 0.0, 0.0);
        assert_eq!(px, vec![128, 128, 128, 255]);
    }
}
