// SPDX-License-Identifier: GPL-3.0-or-later
//! The candidate (選字) window drawn with egui.

use std::sync::Arc;

use egui::epaint::text::{FontData, FontDefinitions};
use egui::{
    Align, Color32, Context, CornerRadius, FontFamily, FontId, Frame, Layout, Margin, RawInput,
    Rect, RichText, Stroke, Vec2, vec2,
};

use crate::raster::{Canvas, Rasterizer};

/// Re-exported so callers do not need their own egui dependency.
pub use egui::Color32 as ExportedColor32;

/// Shared font bytes (for example a memory-mapped file), so fonts are never copied.
pub type FontBlob = Arc<dyn AsRef<[u8]> + Send + Sync>;

/// Everything the candidate window shows.
#[derive(Clone, Debug)]
pub struct CandidateModel {
    pub items: Vec<String>,
    pub selkeys: Vec<char>,
    pub per_row: usize,
    /// 1-based page number and page count for the "1 / 3" badge.
    pub page: usize,
    pub total_pages: usize,
    /// Highlighted item (when the cursor selection is enabled).
    pub selected: Option<usize>,
    pub style: CandidateStyle,
}

#[derive(Clone, Copy, Debug)]
pub struct CandidateStyle {
    pub font_size: f32,
    pub fg: Color32,
    pub selkey: Color32,
    pub highlight_fg: Color32,
    pub highlight_bg: Color32,
    /// Panel fill. Use a translucent colour (or fully transparent when the caller paints a
    /// frosted-glass picture behind the window).
    pub bg: Color32,
    pub border: Color32,
}

impl Default for CandidateStyle {
    /// The classic Chewing look: white panel, black text, blue selection keys, black highlight.
    fn default() -> Self {
        Self {
            font_size: 24.0,
            fg: Color32::BLACK,
            selkey: Color32::from_rgb(0, 0, 255),
            highlight_fg: Color32::WHITE,
            highlight_bg: Color32::BLACK,
            bg: Color32::from_rgb(250, 250, 250),
            border: Color32::from_gray(200),
        }
    }
}

const MARGIN: f32 = 10.0;
const RADIUS: u8 = 8;
const COL_SPACING: f32 = 6.0;
const ROW_SPACING: f32 = 4.0;
const HIGHLIGHT_PAD: Vec2 = vec2(2.0, 2.0);

/// Renders egui frames into pixel buffers. Keep one per window: it owns the font atlas.
pub struct Renderer {
    ctx: Context,
    raster: Rasterizer,
}

impl Renderer {
    /// `fonts` are tried in order for every glyph (first Latin, then CJK, ...). With no fonts egui's
    /// built-in ones are used (no Chinese glyphs).
    pub fn new(fonts: Vec<FontBlob>) -> Self {
        let ctx = Context::default();
        if !fonts.is_empty() {
            let mut defs = FontDefinitions::empty();
            let mut names = Vec::new();
            for (i, blob) in fonts.into_iter().enumerate() {
                let name = format!("font{i}");
                defs.font_data
                    .insert(name.clone(), Arc::new(FontData::from_blob(blob, 0)));
                names.push(name);
            }
            defs.families.insert(FontFamily::Proportional, names.clone());
            defs.families.insert(FontFamily::Monospace, names);
            ctx.set_fonts(defs);
        }
        let mut visuals = egui::Visuals::light();
        visuals.panel_fill = Color32::TRANSPARENT;
        visuals.window_fill = Color32::TRANSPARENT;
        ctx.set_visuals(visuals);
        Self {
            ctx,
            raster: Rasterizer::default(),
        }
    }

    /// Draw the candidate window. `pixels_per_point` is the display scale (1.0 = 96 dpi).
    pub fn render_candidates(&mut self, model: &CandidateModel, pixels_per_point: f32) -> Canvas {
        self.ctx.set_pixels_per_point(pixels_per_point);
        // pass 1: measure the content with generous room
        let (size, _) = self.run(model, Rect::from_min_size(egui::Pos2::ZERO, vec2(4096.0, 4096.0)), false);
        // pass 2: draw into exactly that size
        let (_, canvas) = self.run(model, Rect::from_min_size(egui::Pos2::ZERO, size), true);
        canvas.unwrap_or_else(|| Canvas::new(1, 1))
    }

    fn run(&mut self, model: &CandidateModel, screen: Rect, draw: bool) -> (Vec2, Option<Canvas>) {
        let mut frame_size = Vec2::ZERO;
        let input = RawInput {
            screen_rect: Some(screen),
            ..Default::default()
        };
        let output = self.ctx.run_ui(input, |ui| {
            frame_size = candidate_ui(ui, model);
        });
        self.raster.apply(&output.textures_delta);
        let ppp = output.pixels_per_point;
        let width = (screen.width() * ppp).ceil() as usize;
        let height = (screen.height() * ppp).ceil() as usize;
        let canvas = if draw {
            let prims = self.ctx.tessellate(output.shapes, ppp);
            let mut canvas = Canvas::new(width, height);
            self.raster.paint(&mut canvas, &prims, ppp);
            Some(canvas)
        } else {
            None // the measuring pass: only the layout size matters
        };
        (frame_size, canvas)
    }
}

/// Lay the window out; returns the size of the panel in points.
fn candidate_ui(ui: &mut egui::Ui, model: &CandidateModel) -> Vec2 {
    let st = model.style;
    let font = FontId::proportional(st.font_size);
    let badge_font = FontId::proportional(st.font_size / 1.5);
    let cols = model.per_row.clamp(1, model.items.len().max(1));

    let panel = Frame::new()
        .fill(st.bg)
        .stroke(Stroke::new(0.5, st.border))
        .corner_radius(CornerRadius::same(RADIUS))
        .inner_margin(Margin::same(MARGIN as i8));
    let response = panel.show(ui, |ui| {
        ui.spacing_mut().item_spacing = vec2(COL_SPACING, ROW_SPACING);
        let grid = egui::Grid::new("candidates")
            .spacing(vec2(COL_SPACING, ROW_SPACING))
            .show(ui, |ui| {
                for (i, text) in model.items.iter().enumerate() {
                    let key = model.selkeys.get(i).copied().unwrap_or('?');
                    let selected = model.selected == Some(i);
                    ui.horizontal(|ui| {
                        ui.spacing_mut().item_spacing.x = 0.0;
                        ui.label(RichText::new(format!("{key}.")).font(font.clone()).color(st.selkey));
                        let cell = Frame::new()
                            .fill(if selected { st.highlight_bg } else { Color32::TRANSPARENT })
                            .inner_margin(Margin::symmetric(HIGHLIGHT_PAD.x as i8, HIGHLIGHT_PAD.y as i8));
                        // keep the highlight padding from shifting neighbours: negative outer margin
                        cell.outer_margin(Margin::symmetric(-(HIGHLIGHT_PAD.x as i8), -(HIGHLIGHT_PAD.y as i8)))
                            .show(ui, |ui| {
                                ui.label(
                                    RichText::new(text)
                                        .font(font.clone())
                                        .color(if selected { st.highlight_fg } else { st.fg }),
                                );
                            });
                    });
                    if (i + 1) % cols == 0 {
                        ui.end_row();
                    }
                }
            });
        // the badge is right aligned within the width of the grid (not the whole screen)
        let grid_width = grid.response.rect.width();
        ui.allocate_ui_with_layout(vec2(grid_width, 0.0), Layout::right_to_left(Align::Min), |ui| {
            ui.label(
                RichText::new(format!("{} / {}", model.page, model.total_pages))
                    .font(badge_font)
                    .color(st.fg),
            );
        });
    });
    response.response.rect.size()
}
