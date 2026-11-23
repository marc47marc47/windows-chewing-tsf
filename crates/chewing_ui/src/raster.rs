// SPDX-License-Identifier: GPL-3.0-or-later
//! CPU rasterizer for egui output: textured, vertex-coloured triangles blended into a BGRA canvas.
//!
//! No GPU and no operating-system API: egui tessellates a frame into meshes
//! ([`egui::ClippedPrimitive`]); this module draws them into a premultiplied-alpha pixel buffer that a
//! window system integration can then present (a layered window, a softbuffer surface, a PNG file...).
//! Blending follows egui's default (gamma space, premultiplied alpha), so results match egui's own
//! GPU backends.

use std::collections::HashMap;

use egui::TexturesDelta;
use egui::epaint::{ImageData, Primitive};
use egui::{ClippedPrimitive, Color32, TextureId};

/// A BGRA, premultiplied-alpha, top-down pixel buffer.
#[derive(Clone, Debug)]
pub struct Canvas {
    pub width: usize,
    pub height: usize,
    /// `width * height * 4` bytes, B G R A, premultiplied.
    pub pixels: Vec<u8>,
}

impl Canvas {
    /// A fully transparent canvas.
    pub fn new(width: usize, height: usize) -> Self {
        Self {
            width,
            height,
            pixels: vec![0; width * height * 4],
        }
    }

    /// Encode as a top-down 32-bit BMP (handy for inspection and tests).
    pub fn to_bmp(&self) -> Vec<u8> {
        let mut out = Vec::with_capacity(54 + self.pixels.len());
        out.extend_from_slice(b"BM");
        out.extend_from_slice(&((54 + self.pixels.len()) as u32).to_le_bytes());
        out.extend_from_slice(&[0; 4]);
        out.extend_from_slice(&54u32.to_le_bytes());
        out.extend_from_slice(&40u32.to_le_bytes());
        out.extend_from_slice(&(self.width as i32).to_le_bytes());
        out.extend_from_slice(&(-(self.height as i32)).to_le_bytes());
        out.extend_from_slice(&1u16.to_le_bytes());
        out.extend_from_slice(&32u16.to_le_bytes());
        out.extend_from_slice(&[0; 24]);
        out.extend_from_slice(&self.pixels);
        out
    }
}

struct Texture {
    width: usize,
    height: usize,
    pixels: Vec<Color32>,
}

impl Texture {
    /// Bilinear sample at normalised coordinates (texel centres at +0.5), clamped to the edge.
    fn sample(&self, u: f32, v: f32) -> [f32; 4] {
        let x = (u * self.width as f32 - 0.5).clamp(0.0, self.width as f32 - 1.0);
        let y = (v * self.height as f32 - 0.5).clamp(0.0, self.height as f32 - 1.0);
        let (x0, y0) = (x.floor() as usize, y.floor() as usize);
        let (x1, y1) = ((x0 + 1).min(self.width - 1), (y0 + 1).min(self.height - 1));
        let (fx, fy) = (x - x0 as f32, y - y0 as f32);
        let at = |x: usize, y: usize| {
            let c = self.pixels[y * self.width + x];
            [c.r() as f32, c.g() as f32, c.b() as f32, c.a() as f32]
        };
        let (a, b, c, d) = (at(x0, y0), at(x1, y0), at(x0, y1), at(x1, y1));
        let mut out = [0.0; 4];
        for i in 0..4 {
            let top = a[i] + (b[i] - a[i]) * fx;
            let bottom = c[i] + (d[i] - c[i]) * fx;
            out[i] = top + (bottom - top) * fy;
        }
        out
    }
}

/// Keeps egui's textures (the font atlas, images) and paints frames.
#[derive(Default)]
pub struct Rasterizer {
    textures: HashMap<TextureId, Texture>,
}

impl Rasterizer {
    /// Apply the texture changes of a frame; call before [`Rasterizer::paint`].
    pub fn apply(&mut self, delta: &TexturesDelta) {
        for (id, changes) in &delta.set {
            for change in changes {
                let ImageData::Color(image) = &change.image;
                let [w, h] = image.size;
                match change.pos {
                    None => {
                        self.textures.insert(
                            *id,
                            Texture {
                                width: w,
                                height: h,
                                pixels: image.pixels.clone(),
                            },
                        );
                    }
                    Some([px, py]) => {
                        if let Some(tex) = self.textures.get_mut(id) {
                            for row in 0..h {
                                let dst = (py + row) * tex.width + px;
                                if dst + w <= tex.pixels.len() {
                                    tex.pixels[dst..dst + w]
                                        .copy_from_slice(&image.pixels[row * w..(row + 1) * w]);
                                }
                            }
                        }
                    }
                }
            }
        }
        for id in &delta.free {
            self.textures.remove(id);
        }
    }

    /// Draw tessellated egui output. `pixels_per_point` converts egui points to canvas pixels.
    pub fn paint(&self, canvas: &mut Canvas, primitives: &[ClippedPrimitive], pixels_per_point: f32) {
        for prim in primitives {
            let Primitive::Mesh(mesh) = &prim.primitive else {
                continue;
            };
            let Some(tex) = self.textures.get(&mesh.texture_id) else {
                continue;
            };
            let clip = prim.clip_rect;
            let clip_px = (
                (clip.min.x * pixels_per_point).floor().max(0.0) as i64,
                (clip.min.y * pixels_per_point).floor().max(0.0) as i64,
                ((clip.max.x * pixels_per_point).ceil() as i64).min(canvas.width as i64),
                ((clip.max.y * pixels_per_point).ceil() as i64).min(canvas.height as i64),
            );
            for tri in mesh.indices.chunks_exact(3) {
                let v = [
                    mesh.vertices[tri[0] as usize],
                    mesh.vertices[tri[1] as usize],
                    mesh.vertices[tri[2] as usize],
                ];
                draw_triangle(canvas, tex, &v, pixels_per_point, clip_px);
            }
        }
    }
}

fn draw_triangle(
    canvas: &mut Canvas,
    tex: &Texture,
    v: &[egui::epaint::Vertex; 3],
    ppp: f32,
    clip: (i64, i64, i64, i64),
) {
    // work in canvas pixels; reorder so the signed area is positive (either winding is accepted)
    let mut v = *v;
    let pos = |vt: &egui::epaint::Vertex| (vt.pos.x * ppp, vt.pos.y * ppp);
    let area0 = {
        let (a, b, c) = (pos(&v[0]), pos(&v[1]), pos(&v[2]));
        (b.0 - a.0) * (c.1 - a.1) - (b.1 - a.1) * (c.0 - a.0)
    };
    if area0.abs() < 1e-6 {
        return;
    }
    if area0 < 0.0 {
        v.swap(1, 2);
    }
    let p = [pos(&v[0]), pos(&v[1]), pos(&v[2])];
    let area = area0.abs();
    let min_x = p.iter().map(|q| q.0).fold(f32::MAX, f32::min).floor() as i64;
    let max_x = p.iter().map(|q| q.0).fold(f32::MIN, f32::max).ceil() as i64;
    let min_y = p.iter().map(|q| q.1).fold(f32::MAX, f32::min).floor() as i64;
    let max_y = p.iter().map(|q| q.1).fold(f32::MIN, f32::max).ceil() as i64;
    let (x0, x1) = (min_x.max(clip.0), max_x.min(clip.2));
    let (y0, y1) = (min_y.max(clip.1), max_y.min(clip.3));
    if x0 >= x1 || y0 >= y1 {
        return;
    }
    // Edge function of a->b at point q; >= 0 inside for the positive orientation chosen above.
    let edge = |a: (f32, f32), b: (f32, f32), q: (f32, f32)| (b.0 - a.0) * (q.1 - a.1) - (b.1 - a.1) * (q.0 - a.0);
    // Top-left fill rule: a pixel exactly on an edge belongs to the triangle only if that edge is a
    // "top" or "left" edge, so two triangles sharing an edge never both draw (or both skip) it.
    let owns_edge = |a: (f32, f32), b: (f32, f32)| b.1 < a.1 || (b.1 == a.1 && b.0 > a.0);
    let owns = [owns_edge(p[1], p[2]), owns_edge(p[2], p[0]), owns_edge(p[0], p[1])];
    let inv_area = 1.0 / area;
    let colors = [v[0].color, v[1].color, v[2].color];
    for y in y0..y1 {
        for x in x0..x1 {
            let q = (x as f32 + 0.5, y as f32 + 0.5);
            let e = [edge(p[1], p[2], q), edge(p[2], p[0], q), edge(p[0], p[1], q)];
            if (0..3).any(|i| e[i] < 0.0 || (e[i] == 0.0 && !owns[i])) {
                continue;
            }
            let (w0, w1, w2) = (e[0] * inv_area, e[1] * inv_area, e[2] * inv_area);
            let u = w0 * v[0].uv.x + w1 * v[1].uv.x + w2 * v[2].uv.x;
            let vv = w0 * v[0].uv.y + w1 * v[1].uv.y + w2 * v[2].uv.y;
            let t = tex.sample(u, vv);
            let comps = |col: Color32| [col.r() as f32, col.g() as f32, col.b() as f32, col.a() as f32];
            let (c0, c1, c2) = (comps(colors[0]), comps(colors[1]), comps(colors[2]));
            let mut c = [0.0f32; 4];
            for i in 0..4 {
                let vertex = w0 * c0[i] + w1 * c1[i] + w2 * c2[i];
                c[i] = t[i] * vertex / 255.0; // premultiplied texel * premultiplied vertex colour
            }
            blend(canvas, x as usize, y as usize, c);
        }
    }
}

/// `dst = src + dst * (1 - src.a)` with premultiplied components in 0..=255.
fn blend(canvas: &mut Canvas, x: usize, y: usize, src: [f32; 4]) {
    let i = (y * canvas.width + x) * 4;
    let inv = 1.0 - src[3] / 255.0;
    let d = &mut canvas.pixels[i..i + 4];
    d[0] = (src[2] + d[0] as f32 * inv).round().min(255.0) as u8; // B
    d[1] = (src[1] + d[1] as f32 * inv).round().min(255.0) as u8; // G
    d[2] = (src[0] + d[2] as f32 * inv).round().min(255.0) as u8; // R
    d[3] = (src[3] + d[3] as f32 * inv).round().min(255.0) as u8; // A
}

#[cfg(test)]
mod tests {
    use super::*;
    use egui::epaint::{Mesh, Vertex};
    use egui::{Pos2, Rect, pos2};

    fn white_texture() -> Rasterizer {
        let mut r = Rasterizer::default();
        r.textures.insert(
            TextureId::default(),
            Texture {
                width: 1,
                height: 1,
                pixels: vec![Color32::WHITE],
            },
        );
        r
    }

    fn quad(rect: Rect, color: Color32) -> ClippedPrimitive {
        let mut mesh = Mesh::default();
        let v = |p: Pos2| Vertex {
            pos: p,
            uv: pos2(0.5, 0.5),
            color,
        };
        mesh.vertices = vec![v(rect.left_top()), v(rect.right_top()), v(rect.right_bottom()), v(rect.left_bottom())];
        mesh.indices = vec![0, 1, 2, 0, 2, 3];
        ClippedPrimitive {
            clip_rect: Rect::EVERYTHING,
            primitive: Primitive::Mesh(mesh),
        }
    }

    #[test]
    fn fills_an_opaque_rectangle_and_leaves_the_rest_transparent() {
        let r = white_texture();
        let mut canvas = Canvas::new(8, 8);
        let red = Color32::from_rgb(255, 0, 0);
        r.paint(&mut canvas, &[quad(Rect::from_min_max(pos2(2.0, 2.0), pos2(6.0, 6.0)), red)], 1.0);
        let px = |x: usize, y: usize| canvas.pixels[(y * 8 + x) * 4..(y * 8 + x) * 4 + 4].to_vec();
        assert_eq!(px(3, 3), vec![0, 0, 255, 255]); // BGRA red
        assert_eq!(px(0, 0), vec![0, 0, 0, 0]);
        assert_eq!(px(7, 7), vec![0, 0, 0, 0]);
    }

    #[test]
    fn translucent_colour_blends_over_the_background() {
        let r = white_texture();
        let mut canvas = Canvas::new(4, 4);
        let white = Color32::from_rgb(255, 255, 255);
        let half_black = Color32::from_black_alpha(128);
        let full = Rect::from_min_max(pos2(0.0, 0.0), pos2(4.0, 4.0));
        r.paint(&mut canvas, &[quad(full, white), quad(full, half_black)], 1.0);
        let c = &canvas.pixels[0..4];
        assert!((c[0] as i32 - 127).abs() <= 1, "got {c:?}");
        assert_eq!(c[3], 255);
    }

    #[test]
    fn shared_edge_pixels_are_drawn_exactly_once() {
        // a half-transparent quad is two triangles sharing a diagonal; every pixel must blend once
        let r = white_texture();
        let mut canvas = Canvas::new(6, 6);
        let half = Color32::from_white_alpha(128);
        r.paint(&mut canvas, &[quad(Rect::from_min_max(pos2(0.0, 0.0), pos2(6.0, 6.0)), half)], 1.0);
        for y in 0..6 {
            for x in 0..6 {
                assert_eq!(canvas.pixels[(y * 6 + x) * 4 + 3], 128, "pixel ({x},{y}) blended more or less than once");
            }
        }
    }

    #[test]
    fn clip_rect_limits_drawing() {
        let r = white_texture();
        let mut canvas = Canvas::new(8, 8);
        let mut prim = quad(Rect::from_min_max(pos2(0.0, 0.0), pos2(8.0, 8.0)), Color32::WHITE);
        prim.clip_rect = Rect::from_min_max(pos2(0.0, 0.0), pos2(4.0, 8.0));
        r.paint(&mut canvas, &[prim], 1.0);
        assert_eq!(canvas.pixels[(3) * 4 + 3], 255);
        assert_eq!(canvas.pixels[(5) * 4 + 3], 0);
    }

    #[test]
    fn pixels_per_point_scales_geometry() {
        let r = white_texture();
        let mut canvas = Canvas::new(8, 8);
        r.paint(&mut canvas, &[quad(Rect::from_min_max(pos2(0.0, 0.0), pos2(2.0, 2.0)), Color32::WHITE)], 2.0);
        assert_eq!(canvas.pixels[(3 * 8 + 3) * 4 + 3], 255); // 2 points = 4 pixels
        assert_eq!(canvas.pixels[(5 * 8 + 5) * 4 + 3], 0);
    }
}
