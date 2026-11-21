//! #193（AUD2-16）：夹具必填字段校验门——字段漂移 fail-fast 锁。
//!
//! 审计：fixtures.rs 约 12 处 unwrap_or_default——夹具字段名/类型漂移
//! 静默变空串，下游评分比对拿空串比较（metric_honest_gate 把着的门，
//! 夹具侧漏水）。修复后必填字段（gt_id/category/锚四要素/tc_id/kind/
//! 数据面 path）缺失/空串 → 装载响亮失败。本文件用毒夹具锁三件事：
//!
//! 1. GT 行必填字段缺失 → 拒载（错误信息含文件与字段名）；
//! 2. GT 行必填字段空串 → 拒载（空串比对 = 假比对）；
//! 3. 合法夹具零扰动（既有装载面不误伤）。
//!
//! 注：ET asserts 的 path 对数据面 kind 必填、对 engine_gap/rules_hit
//! （无路径合法面，全量清点实证）放行——由 TC-05/TC-12 真实夹具经
//! fixtures_loaded() 隐式锁定（装载成功即证明白名单正确）。

use bid_grade::fixtures::Fixtures;

/// 最小合法夹具目录骨架（真实文件结构——requirements.jsonl / queries /
/// expected-transitions 三件）。
fn poison_gt_dir(tag: &str, line: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "bid-grade-poison-{tag}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(dir.join("corpus-A/ground-truth")).unwrap();
    std::fs::create_dir_all(dir.join("queries")).unwrap();
    std::fs::create_dir_all(dir.join("corpus-A/expected-transitions")).unwrap();
    std::fs::write(dir.join("corpus-A/ground-truth/requirements.jsonl"), line).unwrap();
    std::fs::write(dir.join("queries/exact-25.jsonl"), "{}\n").unwrap();
    dir
}

/// 必填字段缺失（gt_id 漂移成 gt-id）→ 拒载，错误信息可定位。
#[test]
fn missing_gt_id_rejects_load_with_field_name() {
    let dir = poison_gt_dir(
        "miss-gtid",
        r#"{"gt-id": "GT-99", "category": "资格条件"}"#,
    );
    let err = match Fixtures::load(&dir) {
        Ok(_) => panic!("字段漂移（gt_id→gt-id）必须拒载"),
        Err(e) => e,
    };
    assert!(err.contains("gt_id"), "错误信息含字段名: {err}");
    assert!(err.contains("假比对"), "错误信息说明拒载理由: {err}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// 必填字段空串（category=""）→ 拒载（空串比对 = 假比对——比缺失更隐蔽）。
#[test]
fn empty_category_rejects_load() {
    let dir = poison_gt_dir(
        "empty-cat",
        r#"{"gt_id": "GT-98", "category": ""}"#,
    );
    let err = match Fixtures::load(&dir) {
        Ok(_) => panic!("空串必填字段必须拒载"),
        Err(e) => e,
    };
    assert!(err.contains("category") && err.contains("空串"), "错误信息定位空串字段: {err}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// 锚四要素缺失（excerpt 漂移）→ 拒载。
#[test]
fn missing_anchor_excerpt_rejects_load() {
    let dir = poison_gt_dir(
        "miss-anchor",
        r#"{"gt_id": "GT-97", "category": "资格条件", "anchors": [{"file": "A.docx", "kind": "para", "locator": "行1"}]}"#,
    );
    let err = match Fixtures::load(&dir) {
        Ok(_) => panic!("锚 excerpt 缺失必须拒载"),
        Err(e) => e,
    };
    assert!(err.contains("excerpt"), "错误信息定位锚字段: {err}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// 合法夹具零扰动：真实 corpus-A 装载成功（path 白名单含 engine_gap/
/// rules_hit 的正确性由真实夹具隐式锁定）。
#[test]
fn real_fixtures_load_undisturbed() {
    let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let fixtures_dir = std::env::var("BID_FIXTURES")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| root.join("fixtures"));
    let corpus_a = fixtures_dir.join("corpus-A/files");
    if bid_parse::env_preflight::skip_if_fixture_missing("grade_fixture_gate", &[&corpus_a]) {
        return; // SKIP（夹具不在位——CI 最小面）
    }
    let fx = Fixtures::load(&fixtures_dir).expect("真实夹具装载不得被校验误伤");
    assert!(!fx.gts.is_empty(), "真实 GT 非空");
}
