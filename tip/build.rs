// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Kan-Ru Chen

use std::error::Error;
use std::process::Command;
use std::{env, fs};

/// Seconds since epoch -> "YYYY-MM-DD HH:MM" (UTC), used only when BUILD_TIME is not provided.
fn utc_stamp() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let (days, rem) = (secs.div_euclid(86400), secs.rem_euclid(86400));
    // civil-from-days (Howard Hinnant)
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z.rem_euclid(146097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + i64::from(m <= 2);
    format!("{y:04}-{m:02}-{d:02} {:02}:{:02} UTC", rem / 3600, rem % 3600 / 60)
}

fn git_hash() -> String {
    if let Ok(h) = env::var("BUILD_GIT_HASH") {
        if !h.is_empty() {
            return h;
        }
    }
    Command::new("git")
        .args(["rev-parse", "--short=7", "HEAD"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_else(|| "unknown".into())
}

fn main() -> Result<(), Box<dyn Error>> {
    for v in ["BUILD_VERSION", "BUILD_TIME", "BUILD_GIT_HASH"] {
        println!("cargo:rerun-if-env-changed={v}");
    }
    let version = env::var("BUILD_VERSION")
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| env::var("CARGO_PKG_VERSION").unwrap_or_default());
    let time = env::var("BUILD_TIME")
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(utc_stamp);
    let info = format!("版本 {version} · 編譯 {time} · git {}", git_hash());
    // generated resource header (UTF-8, same encoding as the other .rc files)
    fs::write(
        "rc/buildinfo.h",
        format!("#define BUILD_INFO_STR \"{}\"\n", info.replace('"', "'")),
    )?;
    embed_resource::compile_for_everything("rc/ChewingTextService.rc", embed_resource::NONE)
        .manifest_optional()?;
    Ok(())
}
