//! Enumerate every requested reading against a clean, local dictionary snapshot.
//! Output: reading, rank (0 means unsupported/empty), candidate. No user data is read.
use chewing::{
    conversion::Decoder,
    dictionary::{CompositeDict, LookupStrategy, StringTable},
    lm::{LoadMode, StaticDict, StaticLm},
    user::{HistoryDict, SessionHistoryDict, UserDict},
    zhuyin::Syllable,
};
use std::{
    collections::BTreeSet,
    env,
    error::Error,
    fs,
    io::{self, Write},
    path::Path,
};

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = env::args().collect();
    if args.len() < 3 {
        return Err("usage: candidate_inventory DICTIONARY_DIR SOURCE_CSV ...".into());
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
    let mut readings = BTreeSet::new();
    for source in &args[2..] {
        for line in fs::read_to_string(source)?.lines() {
            if line.starts_with('#') || line.trim().is_empty() {
                continue;
            }
            let (_, reading) = line.split_once(',').ok_or("expected word,bopomofo CSV")?;
            readings.insert(reading.split_whitespace().collect::<Vec<_>>().join(" "));
        }
    }
    let mut output = io::BufWriter::new(io::stdout().lock());
    writeln!(output, "reading\tstatus\trank\tcandidate")?;
    let (mut unsupported, mut empty, mut total) = (0, 0, 0);
    for reading in &readings {
        let syllables = reading
            .split_whitespace()
            .map(str::parse::<Syllable>)
            .collect::<Result<Vec<_>, _>>();
        let syllables = match syllables {
            Ok(s) if !s.is_empty() => s,
            _ => {
                unsupported += 1;
                writeln!(output, "{reading}\tunsupported\t0\t")?;
                continue;
            }
        };
        let candidates = decoder.rank(dict.lookup(&syllables, LookupStrategy::Standard));
        if candidates.is_empty() {
            empty += 1;
            writeln!(output, "{reading}\tempty\t0\t")?;
        }
        for (index, candidate) in candidates.iter().enumerate() {
            let text = st
                .get_text(candidate.wid)
                .ok_or("candidate has missing text")?;
            writeln!(output, "{reading}\tok\t{}\t{text}", index + 1)?;
            total += 1;
        }
    }
    output.flush()?;
    eprintln!(
        "readings={} candidates={total} unsupported={unsupported} empty={empty}",
        readings.len()
    );
    Ok(())
}
