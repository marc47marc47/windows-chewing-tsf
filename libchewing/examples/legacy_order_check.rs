//! Exhaustively check the legacy-order implementation against the exported Microsoft table.
//! usage: legacy_order_check DICTIONARY_DIR MS_ORDER_TSV
//! For every reading of the table: dictionary candidates -> LegacyOrder::sort -> verify that candidates
//! having an ordinal appear in ascending ordinal order, all of them before those without, and that
//! the count of candidates is unchanged.  Prints one summary line and a few violations.
use chewing::{
    dictionary::{CompositeDict, LookupStrategy, StringTable},
    editor::legacy_order::LegacyOrder,
    lm::StaticDict,
    user::{HistoryDict, SessionHistoryDict, UserDict},
    zhuyin::Syllable,
};
use std::{collections::BTreeSet, error::Error, fs, io::BufReader, path::Path, str::FromStr};

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() != 3 {
        return Err("usage: legacy_order_check DICTIONARY_DIR MS_ORDER_TSV".into());
    }
    let dir = Path::new(&a[1]);
    let st = StringTable::open_bin(dir.join("static_words.bin"))?;
    let dict = CompositeDict::new(
        StaticDict::open(dir.join("static_dict.bin"))?,
        StaticDict::open(dir.join("rare_dict.bin"))?,
        HistoryDict::new(st.clone()),
        SessionHistoryDict::new(st.clone()),
        UserDict::new(st.clone()),
    );
    let table = LegacyOrder::from_tsv(BufReader::new(fs::File::open(&a[2])?))?;
    let mut readings = BTreeSet::new();
    for line in fs::read_to_string(&a[2])?.lines() {
        if let Some(r) = line.split('\t').next() {
            readings.insert(r.to_string());
        }
    }
    let (mut checked, mut cands, mut with_ord, mut bad) = (0usize, 0usize, 0usize, 0usize);
    for r in &readings {
        let Ok(syl) = Syllable::from_str(r) else { continue };
        let words = dict.lookup(&[syl], LookupStrategy::Standard);
        let n = words.len();
        let sorted = table.sort(&[syl], words, |c| st.get_text(c.wid).unwrap_or_default());
        assert_eq!(n, sorted.len());
        checked += 1;
        cands += n;
        let mut last: Option<u16> = None;
        let mut seen_none = false;
        let mut ok = true;
        let mut prev_len = 0usize;
        for c in &sorted {
            let t = st.get_text(c.wid).unwrap_or_default();
            let len = t.chars().count();
            if len < prev_len {
                ok = false;
            }
            if len != prev_len {
                last = None;
                seen_none = false;
            }
            prev_len = len;
            match table.ordinal(&syl, &t) {
                Some(o) => {
                    with_ord += 1;
                    if seen_none || last.map_or(false, |l| o < l) {
                        ok = false;
                    }
                    last = Some(o);
                }
                None => seen_none = true,
            }
        }
        if !ok {
            bad += 1;
            if bad <= 5 {
                eprintln!("violation: {r}");
            }
        }
    }
    println!("readings_checked={checked} candidates={cands} with_ordinal={with_ord} violations={bad} skipped_rows={}", table.skipped_rows());
    if bad > 0 {
        std::process::exit(1);
    }
    Ok(())
}
