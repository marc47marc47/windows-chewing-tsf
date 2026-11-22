//! Microsoft Bopomofo "fixed candidate order" (legacy order) for candidate lists.
//!
//! Reverse-engineered from IMTCCORE `CStncCandList::NewCompItemLegacy` (180059db0): candidates are
//! ordered by (1) text length ascending, (2) the per-reading legacy ordinal of a character when both
//! candidates have one, a candidate with an ordinal sorting before one without, (3) otherwise the
//! Unicode sequence with CJK Extension A (U+3400..U+4DB5) placed after the other BMP characters and
//! supplementary-plane characters last, (4) finally the original position.
//!
//! The ordinals come from a data table exported from the system lexicon
//! (`analyze/p3/ms-char-order.tsv`): `reading <TAB> source <TAB> a|b|c`, ordinal = position in the list
//! of that row.  The table is optional; without it only steps (1), (3) and (4) apply.

use std::{
    collections::HashMap,
    io::{self, BufRead},
    str::FromStr,
    sync::Arc,
};

use crate::zhuyin::Syllable;

/// Sentinel used by the Microsoft data for "no ordinal".
pub const NO_ORDINAL: u16 = 0xffff;

#[derive(Debug, Default, Clone)]
pub struct LegacyOrder {
    ranks: HashMap<Syllable, HashMap<String, u16>>,
    skipped_rows: usize,
}

impl LegacyOrder {
    pub fn new() -> LegacyOrder {
        LegacyOrder::default()
    }

    /// Parse the TSV export.  Rows whose reading is not a single valid syllable are counted, not fatal.
    pub fn from_tsv<R: BufRead>(reader: R) -> io::Result<LegacyOrder> {
        let mut table = LegacyOrder::new();
        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() || line.starts_with('#') {
                continue;
            }
            let mut parts = line.splitn(3, '\t');
            let (Some(reading), Some(_source), Some(chars)) = (parts.next(), parts.next(), parts.next())
            else {
                table.skipped_rows += 1;
                continue;
            };
            let Ok(syllable) = Syllable::from_str(reading) else {
                table.skipped_rows += 1;
                continue;
            };
            let entry = table.ranks.entry(syllable).or_default();
            for (i, ch) in chars.split('|').filter(|c| !c.is_empty()).enumerate() {
                // keep the first (lowest) ordinal if the same character is listed twice
                entry.entry(ch.to_string()).or_insert(i.min(NO_ORDINAL as usize - 1) as u16);
            }
        }
        Ok(table)
    }

    pub fn len(&self) -> usize {
        self.ranks.len()
    }

    pub fn is_empty(&self) -> bool {
        self.ranks.is_empty()
    }

    pub fn skipped_rows(&self) -> usize {
        self.skipped_rows
    }

    pub fn ordinal(&self, syllable: &Syllable, text: &str) -> Option<u16> {
        self.ranks.get(syllable)?.get(text).copied()
    }

    /// Stable-sort `items` (text, original index implied by position) into Microsoft legacy order.
    /// `syllables` is the reading of the list; ordinals apply only to single-syllable readings.
    pub fn sort<T>(&self, syllables: &[Syllable], items: Vec<T>, text_of: impl Fn(&T) -> String) -> Vec<T> {
        let single = if syllables.len() == 1 { Some(&syllables[0]) } else { None };
        let mut keyed: Vec<_> = items
            .into_iter()
            .enumerate()
            .map(|(idx, item)| {
                let text = text_of(&item);
                let ordinal = single.and_then(|s| self.ordinal(s, &text));
                (sort_key(&text, ordinal, idx), item)
            })
            .collect();
        keyed.sort_by(|a, b| a.0.cmp(&b.0));
        keyed.into_iter().map(|(_, item)| item).collect()
    }
}

/// Shared handle stored in the editor.
pub type SharedLegacyOrder = Arc<LegacyOrder>;

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) struct SortKey {
    len: usize,
    group: u8,
    ordinal: u16,
    unicode: Vec<u64>,
    index: usize,
}

fn unicode_key(c: char) -> u64 {
    let v = c as u32;
    if v > 0xffff {
        (1u64 << 32) + v as u64
    } else if (0x3400..=0x4db5).contains(&v) {
        (v | 0x10000) as u64
    } else {
        v as u64
    }
}

pub(crate) fn sort_key(text: &str, ordinal: Option<u16>, index: usize) -> SortKey {
    let len = text.chars().count();
    match ordinal {
        Some(o) => SortKey { len, group: 0, ordinal: o, unicode: Vec::new(), index },
        None => SortKey { len, group: 1, ordinal: 0, unicode: text.chars().map(unicode_key).collect(), index },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{syl, zhuyin::Bopomofo::*};

    fn table() -> LegacyOrder {
        // reading ㄕˋ: 市 是 事 in Microsoft order
        let tsv = "ㄕˋ\tIMTCPH\t市|是|事\nbad\tIMTCPH\tx\n";
        LegacyOrder::from_tsv(tsv.as_bytes()).unwrap()
    }

    #[test]
    fn parses_and_counts_skipped_rows() {
        let t = table();
        assert_eq!(1, t.len());
        assert_eq!(1, t.skipped_rows());
        assert_eq!(Some(0), t.ordinal(&syl![SH, TONE4], "市"));
        assert_eq!(Some(2), t.ordinal(&syl![SH, TONE4], "事"));
        assert_eq!(None, t.ordinal(&syl![SH, TONE4], "式"));
    }

    #[test]
    fn single_syllable_uses_ordinals_then_unicode() {
        let t = table();
        let items = vec!["事", "式", "是", "市", "氏"];
        let sorted = t.sort(&[syl![SH, TONE4]], items, |s| s.to_string());
        // ordinals first (市 是 事), then characters without ordinal in Unicode order (氏 U+6C0F < 式 U+5F0F? no: 式 < 氏)
        assert_eq!(vec!["市", "是", "事", "式", "氏"], sorted);
    }

    #[test]
    fn shorter_text_first_and_ext_a_after_bmp() {
        let t = LegacyOrder::new();
        let items = vec!["一二", "㐀", "乙", "丁", "𠀀"];
        let sorted = t.sort(&[syl![SH, TONE4]], items, |s| s.to_string());
        // length 1 first: BMP (丁 U+4E01, 乙 U+4E59), then Ext A 㐀 (U+3400), then supplementary; then length 2
        assert_eq!(vec!["丁", "乙", "㐀", "𠀀", "一二"], sorted);
    }

    #[test]
    fn multi_syllable_has_no_ordinals_and_is_stable() {
        let t = table();
        let sorted = t.sort(&[syl![SH, TONE4], syl![SH, TONE4]], vec!["是事", "市是", "市事"], |s| s.to_string());
        assert_eq!(vec!["市事", "市是", "是事"], sorted);
        let same = t.sort(&[syl![SH, TONE4]], vec!["x", "x"], |s| s.to_string());
        assert_eq!(2, same.len());
    }
}
