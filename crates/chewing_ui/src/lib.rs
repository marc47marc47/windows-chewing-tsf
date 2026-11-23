// SPDX-License-Identifier: GPL-3.0-or-later
//! egui based UI for the Chewing IME, rendered on the CPU.
//!
//! The crate is plain Rust with no operating-system API: callers supply fonts and present the pixels.

pub mod candidate;
pub mod raster;
