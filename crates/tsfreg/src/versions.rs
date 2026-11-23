//! Versioned install directories (`<root>\26.11.1125`, Chrome style).
//! The stable stub DLL in `<root>` loads the newest one; the installer keeps only the newest [`KEEP`].

use std::fs;
use std::path::{Path, PathBuf};

/// Number of version directories kept after an install.
pub const KEEP: usize = 2;

/// "26.11.1125" -> [26, 11, 1125]. Names that are not dotted numbers are not version directories.
pub fn parse_version(name: &str) -> Option<Vec<u64>> {
    let parts: Option<Vec<u64>> = name.split('.').map(|p| p.parse().ok()).collect();
    parts.filter(|p| p.len() >= 2)
}

/// Version directories under `root`, newest first.
pub fn list(root: &Path) -> Vec<(Vec<u64>, PathBuf)> {
    let mut dirs: Vec<_> = fs::read_dir(root)
        .into_iter()
        .flatten()
        .flatten()
        .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
        .filter_map(|e| {
            let v = parse_version(&e.file_name().to_string_lossy())?;
            Some((v, e.path()))
        })
        .collect();
    dirs.sort_by(|a, b| b.0.cmp(&a.0));
    dirs
}

/// Delete every version directory except the newest `keep`. Files still loaded by a running
/// program cannot be deleted; they are skipped and removed by a later prune.
pub fn prune(root: &Path, keep: usize) -> Vec<PathBuf> {
    let mut removed = vec![];
    for (_, dir) in list(root).into_iter().skip(keep) {
        if fs::remove_dir_all(&dir).is_ok() {
            removed.push(dir);
        } else {
            // best effort: drop whatever is not in use so the directory is never picked up again
            let _ = fs::remove_file(dir.join("chewing_tip_impl.dll"));
        }
    }
    removed
}

/// Clean up the old Chrome-style layout (version folders + the stable stub `chewing_tip.dll`)
/// left behind when upgrading to the System32 layout. Does nothing when `root` has no version
/// folder, so a plain installation is never touched. Files still loaded by a program are skipped.
pub fn legacy_cleanup(root: &Path) -> Vec<PathBuf> {
    if list(root).is_empty() {
        return vec![];
    }
    let mut removed = prune(root, 0);
    let stub = root.join("chewing_tip.dll");
    if fs::remove_file(&stub).is_ok() {
        removed.push(stub);
    }
    removed
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("tsfreg_ver_{name}_{}", std::process::id()));
        let _ = fs::remove_dir_all(&p);
        fs::create_dir_all(&p).unwrap();
        p
    }

    #[test]
    fn parse_orders_numerically() {
        assert!(parse_version("26.11.1125") > parse_version("26.11.999"));
        assert_eq!(parse_version("Dictionary"), None);
        assert_eq!(parse_version("26"), None);
    }

    #[test]
    fn keeps_newest_two() {
        let root = tmp("keep");
        for v in ["26.11.999", "26.11.1123", "26.11.1124", "26.11.1125"] {
            fs::create_dir_all(root.join(v)).unwrap();
        }
        fs::create_dir_all(root.join("other")).unwrap();
        let removed = prune(&root, KEEP);
        assert_eq!(removed.len(), 2);
        let left: Vec<_> = list(&root).into_iter().map(|(_, p)| p.file_name().unwrap().to_string_lossy().to_string()).collect();
        assert_eq!(left, vec!["26.11.1125", "26.11.1124"]);
        assert!(root.join("other").exists());
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn purge_removes_all_versions_only() {
        let root = tmp("purge");
        fs::create_dir_all(root.join("26.11.1")).unwrap();
        fs::create_dir_all(root.join("keepme")).unwrap();
        prune(&root, 0);
        assert!(!root.join("26.11.1").exists());
        assert!(root.join("keepme").exists());
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn legacy_cleanup_removes_stub_only_with_version_folders() {
        let plain = tmp("legacy_plain");
        fs::write(plain.join("chewing_tip.dll"), b"x").unwrap();
        assert!(legacy_cleanup(&plain).is_empty());
        assert!(plain.join("chewing_tip.dll").exists());

        let old = tmp("legacy_old");
        fs::write(old.join("chewing_tip.dll"), b"x").unwrap();
        fs::create_dir_all(old.join("26.11.1130")).unwrap();
        fs::create_dir_all(old.join("Dictionary")).unwrap();
        let removed = legacy_cleanup(&old);
        assert_eq!(removed.len(), 2);
        assert!(!old.join("chewing_tip.dll").exists());
        assert!(!old.join("26.11.1130").exists());
        assert!(old.join("Dictionary").exists());
        let _ = fs::remove_dir_all(&plain);
        let _ = fs::remove_dir_all(&old);
    }
}
