//! Render the candidate window to a BMP file for inspection.
//! usage: candidate_bmp OUT.bmp FONT.ttf [PIXELS_PER_POINT]
use std::sync::Arc;

use chewing_ui::candidate::{CandidateModel, CandidateStyle, FontBlob, Renderer};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.get(1).expect("OUT.bmp");
    let font: FontBlob = Arc::new(std::fs::read(args.get(2).expect("FONT.ttf")).expect("read font"));
    let ppp: f32 = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(1.0);

    let model = CandidateModel {
        items: "測側冊策廁冊厠鍘筴惻".chars().map(|c| c.to_string()).collect(),
        selkeys: "1234567890".chars().collect(),
        per_row: 10,
        page: 1,
        total_pages: 3,
        selected: Some(0),
        style: CandidateStyle::default(),
    };
    let started = std::time::Instant::now();
    let mut renderer = Renderer::new(vec![font]);
    let created = started.elapsed();
    let canvas = renderer.render_candidates(&model, ppp);
    let first = started.elapsed();
    let again = std::time::Instant::now();
    let _ = renderer.render_candidates(&model, ppp);
    println!(
        "{}x{} px; setup {:?}, first frame {:?}, repeat frame {:?}",
        canvas.width,
        canvas.height,
        created,
        first - created,
        again.elapsed()
    );
    std::fs::write(out, canvas.to_bmp()).expect("write bmp");
}
