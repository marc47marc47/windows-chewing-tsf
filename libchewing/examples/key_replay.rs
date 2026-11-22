//! Replay a key script against the local chewing Editor with isolated, in-memory user data.
//! usage: key_replay DICTIONARY_DIR [--space-select] [--cycle-n N] [--ms-order TSV] [--page-size N] KEY...
//! KEY is a single ASCII character (standard zhuyin layout) or one of:
//!   <SPACE> <ENTER> <ESC> <DOWN> <UP> <LEFT> <RIGHT> <PGUP> <PGDN> <HOME> <END> <BKSP> <TAB> <DEL>
//! Output: one JSON object per key (state after the key). No personal/user dictionary is read or written.
use chewing::{
    dictionary::StringTable,
    editor::{BasicEditor, EditorBuilder},
    input::{
        keycode::*,
        keymap::{QWERTY_MAP, map_ascii},
        keysym::*,
        KeyboardEvent,
    },
    editor::Editor,
    lm::{LoadMode, StaticDict, StaticLm},
};
use chewing::editor::legacy_order::LegacyOrder;
use std::{env, error::Error, path::Path};

fn special(tok: &str) -> Option<KeyboardEvent> {
    let (code, sym) = match tok {
        "<SPACE>" => (KEY_SPACE, SYM_SPACE),
        "<ENTER>" => (KEY_ENTER, SYM_RETURN),
        "<ESC>" => (KEY_ESC, SYM_ESC),
        "<DOWN>" => (KEY_DOWN, SYM_DOWN),
        "<UP>" => (KEY_UP, SYM_UP),
        "<LEFT>" => (KEY_LEFT, SYM_LEFT),
        "<RIGHT>" => (KEY_RIGHT, SYM_RIGHT),
        "<PGUP>" => (KEY_PAGEUP, SYM_PAGEUP),
        "<PGDN>" => (KEY_PAGEDOWN, SYM_PAGEDOWN),
        "<HOME>" => (KEY_HOME, SYM_HOME),
        "<END>" => (KEY_END, SYM_END),
        "<BKSP>" => (KEY_BACKSPACE, SYM_BACKSPACE),
        "<TAB>" => (KEY_TAB, SYM_TAB),
        "<DEL>" => (KEY_DELETE, SYM_DELETE),
        _ => return None,
    };
    Some(KeyboardEvent::builder().code(code).ksym(sym).build())
}

fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        return Err("usage: key_replay DICTIONARY_DIR [--space-select] [--cycle-n N] KEY...".into());
    }
    let dir = Path::new(&args[1]);
    let mut space_select = false;
    let mut cycle_n = 0usize;
    let mut ms_order: Option<String> = None;
    let mut page_size: Option<usize> = None;
    let mut user_dir: Option<String> = None;
    let mut sort_freq = false;
    let mut engine: Option<String> = None;
    let mut add_backward = false;
    let mut keys = Vec::new();
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--space-select" => space_select = true,
            "--ms-order" => {
                i += 1;
                ms_order = Some(args[i].clone());
            }
            "--user-dir" => {
                i += 1;
                user_dir = Some(args[i].clone());
            }
            "--sort-by-frequency" => sort_freq = true,
            "--add-backward" => add_backward = true,
            "--engine" => {
                i += 1;
                engine = Some(args[i].clone());
            }
            "--page-size" => {
                i += 1;
                page_size = Some(args[i].parse()?);
            }
            "--cycle-n" => {
                i += 1;
                cycle_n = args[i].parse()?;
            }
            k => keys.push(k.to_string()),
        }
        i += 1;
    }
    let mut editor = if let Some(ud) = &user_dir {
        // real-profile behaviour: dictionaries + a COPY of the user's data directory (never the original)
        Editor::chewing(Some(dir.to_string_lossy().to_string()), Some(ud.clone()))?
    } else {
        let st = StringTable::open_bin(dir.join("static_words.bin"))?;
        EditorBuilder::new()
            .string_table(st)
            .static_dict(StaticDict::open(dir.join("static_dict.bin"))?)
            .rare_dict(StaticDict::open(dir.join("rare_dict.bin"))?)
            .static_lm(StaticLm::open(dir.join("static_lm.bin"), LoadMode::Lazy)?)
            .build()
    };
    editor.set_editor_options(|o| {
        o.space_is_select_key = space_select;
        o.cycle_first_n_selects = cycle_n;
        o.ms_legacy_candidate_order = ms_order.is_some();
        o.sort_candidates_by_frequency = sort_freq;
        if add_backward {
            o.user_phrase_add_dir = chewing::editor::UserPhraseAddDirection::Backward;
        }
        match engine.as_deref() {
            Some("simple") => o.conversion_engine = chewing::editor::ConversionEngineKind::SimpleEngine,
            Some("fuzzy") => o.conversion_engine = chewing::editor::ConversionEngineKind::FuzzyChewingEngine,
            _ => {}
        }
        if let Some(n) = page_size {
            o.candidates_per_page = n;
        }
    });
    if let Some(path) = &ms_order {
        let table = LegacyOrder::from_tsv(std::io::BufReader::new(std::fs::File::open(path)?))?;
        eprintln!("ms-order readings={} skipped_rows={}", table.len(), table.skipped_rows());
        editor.set_legacy_order(table);
    }
    for tok in &keys {
        let ev = match special(tok) {
            Some(ev) => ev,
            None if tok.starts_with("<CTRL+") && tok.ends_with('>') && tok.len() == 8 => {
                let d = tok.as_bytes()[6];
                let mut ev = map_ascii(&QWERTY_MAP, d);
                ev = KeyboardEvent::builder().code(ev.code).ksym(ev.ksym).control().build();
                ev
            }
            None if tok.len() == 1 => map_ascii(&QWERTY_MAP, tok.as_bytes()[0]),
            None => return Err(format!("bad key token {tok}").into()),
        };
        let behavior = editor.process_keyevent(ev);
        let commit = editor.display_commit().to_string();
        let per_page = editor.editor_options().candidates_per_page;
        let page = editor
            .paginated_candidates()
            .unwrap_or_default()
            .into_iter()
            .take(per_page)
            .collect::<Vec<_>>()
            .join("|");
        let (pno, ptotal) = (
            editor.current_page_no().map(|n| n as i64).unwrap_or(-1),
            editor.total_page().map(|n| n as i64).unwrap_or(-1),
        );
        println!(
            "{{\"key\":\"{}\",\"behavior\":\"{:?}\",\"selecting\":{},\"entering_syllable\":{},\"display\":\"{}\",\"syllable\":\"{}\",\"cursor\":{},\"commit\":\"{}\",\"page\":{},\"total_pages\":{},\"candidates\":\"{}\",\"notice\":\"{}\"}}",
            esc(tok),
            behavior,
            editor.is_selecting(),
            editor.entering_syllable(),
            esc(&editor.display()),
            esc(&editor.syllable_buffer_display()),
            editor.cursor(),
            esc(&commit),
            pno,
            ptotal,
            esc(&page),
            esc(editor.notification())
        );
        if !commit.is_empty() {
            editor.ack();
        }
    }
    Ok(())
}
