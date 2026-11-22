//! Batch sentence conversion with the local chewing Editor (isolated, in-memory user data).
//! usage: convert_batch DICTIONARY_DIR CORPUS_TSV      rows: id <TAB> kind <TAB> reading <TAB> keys ('_' = Space)
//! output: one JSON object per row {"id","kind","reading","chewing"}
use chewing::{
    dictionary::StringTable,
    editor::{BasicEditor, EditorBuilder},
    input::{
        keycode::KEY_SPACE,
        keymap::{QWERTY_MAP, map_ascii},
        keysym::SYM_SPACE,
        KeyboardEvent,
    },
    lm::{LoadMode, StaticDict, StaticLm},
};
use std::{env, error::Error, fs, path::Path};

fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().collect();
    if a.len() != 3 {
        return Err("usage: convert_batch DICTIONARY_DIR CORPUS_TSV".into());
    }
    let dir = Path::new(&a[1]);
    let st = StringTable::open_bin(dir.join("static_words.bin"))?;
    let mut editor = EditorBuilder::new()
        .string_table(st)
        .static_dict(StaticDict::open(dir.join("static_dict.bin"))?)
        .rare_dict(StaticDict::open(dir.join("rare_dict.bin"))?)
        .static_lm(StaticLm::open(dir.join("static_lm.bin"), LoadMode::Lazy)?)
        .build();
    editor.set_editor_options(|o| o.auto_commit_threshold = 1000);
    for line in fs::read_to_string(&a[2])?.lines() {
        let p: Vec<&str> = line.split('\t').collect();
        if p.len() < 4 {
            continue;
        }
        for ch in p[3].bytes() {
            let ev = if ch == b'_' {
                KeyboardEvent::builder().code(KEY_SPACE).ksym(SYM_SPACE).build()
            } else {
                map_ascii(&QWERTY_MAP, ch)
            };
            editor.process_keyevent(ev);
        }
        let mut shown = editor.display();
        let tail = editor.syllable_buffer_display();
        if !tail.is_empty() {
            shown.push_str(&tail);
        }
        println!(
            "{{\"id\":\"{}\",\"kind\":\"{}\",\"reading\":\"{}\",\"chewing\":\"{}\"}}",
            p[0], p[1], esc(p[2]), esc(&shown)
        );
        editor.clear();
    }
    Ok(())
}
