//! Two Editor instances (like two applications each hosting the TIP) share one user data directory.
//! A learns phrase X, B (loaded BEFORE A flushed) learns phrase Y; afterwards both must be in user_dict.csv.
use chewing::{
    editor::{BasicEditor, Editor, UserPhraseAddDirection},
    input::{keymap::{QWERTY_MAP, map_ascii}, keysym::SYM_2, KeyboardEvent},
};
use std::{env, error::Error, fs};

fn type_keys(e: &mut Editor, keys: &str) {
    for b in keys.bytes() {
        e.process_keyevent(map_ascii(&QWERTY_MAP, b));
    }
}
fn ctrl2(e: &mut Editor) {
    let ev = map_ascii(&QWERTY_MAP, b'2');
    e.process_keyevent(KeyboardEvent::builder().code(ev.code).ksym(SYM_2).control().build());
}

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().collect();
    let (dict, user) = (a[1].clone(), a[2].clone());
    let mut ea = Editor::chewing(Some(dict.clone()), Some(user.clone()))?;
    let mut eb = Editor::chewing(Some(dict.clone()), Some(user.clone()))?;   // loaded before A writes
    for e in [&mut ea, &mut eb] {
        e.set_editor_options(|o| o.user_phrase_add_dir = UserPhraseAddDirection::Backward);
    }
    type_keys(&mut ea, "hk4g4bp4j4"); // 測試任務
    ctrl2(&mut ea);                    // learns 任務
    println!("A notice: {}", ea.notification());
    type_keys(&mut eb, "su3cl3");     // 你好
    ctrl2(&mut eb);                    // learns 你好
    println!("B notice: {}", eb.notification());
    let text = fs::read_to_string(format!("{user}/v4/user_dict.csv"))?;
    println!("user_dict has 任務: {}", text.contains("任務,"));
    println!("user_dict has 你好: {}", text.contains("你好,"));
    Ok(())
}
