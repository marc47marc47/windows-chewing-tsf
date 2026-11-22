//! Print the dictionary's own candidate order (no language-model ranking) for readings.
//! usage: raw_order DICTIONARY_DIR READINGS_FILE      (one reading per line, syllables separated by spaces)
//! output: reading <TAB> ranked(0|1) <TAB> candidates joined by '|'   (raw order, then ranked order)
use chewing::{
    conversion::Decoder,
    dictionary::{CompositeDict, LookupStrategy, StringTable},
    lm::{LoadMode, StaticDict, StaticLm},
    user::{HistoryDict, SessionHistoryDict, UserDict},
    zhuyin::Syllable,
};
use std::{
    error::Error,
    fs,
    io::{self, Write},
    path::Path,
};

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 3 {
        return Err("usage: raw_order DICTIONARY_DIR READINGS_FILE".into());
    }
    let dir = Path::new(&args[1]);
    let st = StringTable::open_bin(dir.join("static_words.bin"))?;
    let history = HistoryDict::new(st.clone());
    let dict = CompositeDict::new(
        StaticDict::open(dir.join("static_dict.bin"))?,
        StaticDict::open(dir.join("rare_dict.bin"))?,
        history.clone(),
        SessionHistoryDict::new(st.clone()),
        UserDict::new(st.clone()),
    );
    let decoder = Decoder {
        lm: StaticLm::open(dir.join("static_lm.bin"), LoadMode::Lazy)?,
        hist: history,
        lambda: Decoder::LAMBDA,
    };
    let mut out = io::BufWriter::new(io::stdout().lock());
    for line in fs::read_to_string(&args[2])?.lines() {
        let reading = line.trim();
        if reading.is_empty() {
            continue;
        }
        let syllables = match reading
            .split_whitespace()
            .map(str::parse::<Syllable>)
            .collect::<Result<Vec<_>, _>>()
        {
            Ok(s) if !s.is_empty() => s,
            _ => {
                writeln!(out, "{reading}\tunsupported\t")?;
                continue;
            }
        };
        let raw = dict.lookup(&syllables, LookupStrategy::Standard);
        let text = |c: &chewing::dictionary::CompositeWord| st.get_text(c.wid).unwrap_or_default().to_string();
        writeln!(out, "{reading}\t0\t{}", raw.iter().map(text).collect::<Vec<_>>().join("|"))?;
        let ranked = decoder.rank(raw);
        writeln!(out, "{reading}\t1\t{}", ranked.iter().map(text).collect::<Vec<_>>().join("|"))?;
    }
    out.flush()?;
    Ok(())
}
