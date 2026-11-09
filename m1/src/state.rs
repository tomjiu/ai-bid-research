//! state.rs — 后端权威状态机（研究验证 M1 子集）
//!
//! 实现范围（与 docs/bid-domain-model.md 的状态子集对齐，M1 只开放已实现工具）：
//!   INIT → DRAFT → FILES_IMPORTED → REQUIREMENTS_EXTRACTED
//! 守卫：未实现/越级工具一律 E_STATE 且零副作用（TC-11 越级防护）。
//! 幂等键表：file sha256 → file_id（TC-07 重放 no-op）；project external_ref 幂等。

use std::collections::HashMap;

pub const E_STATE: &str = "E_STATE";

pub struct Machine {
    pub status: String,
    pub content_version: u32,
    pub project_id: Option<String>,
    idem_files: HashMap<String, String>, // sha256 → file_id（内容寻址幂等）
    idem_projects: HashMap<String, String>, // external_ref → project_id
    pub last_error: Option<String>,
}

impl Machine {
    pub fn new() -> Self {
        Machine {
            status: "INIT".into(),
            content_version: 0,
            project_id: None,
            idem_files: HashMap::new(),
            idem_projects: HashMap::new(),
            last_error: None,
        }
    }

    /// 项目幂等：同 external_ref 重放 create → 返回原 project_id，状态不变（no-op）。
    pub fn create_project(&mut self, external_ref: &str) -> String {
        if let Some(pid) = self.idem_projects.get(external_ref) {
            return pid.clone();
        }
        let pid = format!("P-{}", &crate::contract::content_hash(&[external_ref, "project"])[..10]);
        self.idem_projects.insert(external_ref.into(), pid.clone());
        self.project_id = Some(pid.clone());
        self.status = "DRAFT".into();
        pid
    }

    /// 文件幂等：同 sha256 重放 import → 返回 None 表示 no-op（不产生新块、不变更状态）。
    pub fn import_file(&mut self, sha256: &str, _kind: &str, file_name: &str) -> Option<String> {
        if self.idem_files.get(sha256).is_some() {
            return None; // no-op：调用方从 file_id_of 取原 file_id
        }
        let fid = format!("F-{}", &crate::contract::content_hash(&[sha256, file_name])[..10]);
        self.idem_files.insert(sha256.into(), fid.clone());
        Some(fid)
    }

    pub fn file_id_of(&self, sha256: &str) -> Option<String> {
        self.idem_files.get(sha256).cloned()
    }

    /// 工具门禁 + 状态转换。返回 Err(E_STATE) 表示越级/未实现工具（零副作用）。
    pub fn call_tool(&mut self, tool: &str) -> Result<String, String> {
        let st = self.status.as_str();
        let next: Result<String, String> = match tool {
            "create_bid_project" => {
                if st == "INIT" || st == "DRAFT" {
                    Ok("DRAFT".to_string())
                } else {
                    return self.reject(tool);
                }
            }
            "import_tender_files" => {
                // 主导入（DRAFT/FILES_IMPORTED）与补遗/增量导入（REQUIREMENTS_EXTRACTED，TC-09 骨架）均合法
                if st == "DRAFT" || st == "FILES_IMPORTED" || st == "REQUIREMENTS_EXTRACTED" {
                    Ok("FILES_IMPORTED".to_string())
                } else {
                    return self.reject(tool);
                }
            }
            "extract_requirements" => {
                if st == "FILES_IMPORTED" || st == "REQUIREMENTS_EXTRACTED" {
                    Ok("REQUIREMENTS_EXTRACTED".to_string())
                } else {
                    return self.reject(tool);
                }
            }
            "search_evidence" | "chunk_corpus" => {
                // 检索/切块：语料在位后任意后续状态可用（纯读，不改状态）
                if st == "FILES_IMPORTED" || st == "REQUIREMENTS_EXTRACTED" {
                    Ok(st.to_string())
                } else {
                    return self.reject(tool);
                }
            }
            // ---- 以下工具属 M2~M5 里程碑：M1 阶段一律 E_STATE（防越级造绿）----
            "build_compliance_matrix" | "attach_evidence" | "draft_outline"
            | "draft_response_section" | "validate_bid_document" | "export_bid_document"
            | "record_review_decision" | "create_revision_task" => {
                return self.reject(tool);
            }
            _ => return Err(format!("E_TOOL_UNKNOWN:{}", tool)),
        };
        self.status = next?;
        self.last_error = None;
        Ok(self.status.clone())
    }

    fn reject(&mut self, tool: &str) -> Result<String, String> {
        // 零副作用：不改状态、不入幂等表——last_error 仅记录，产物以 trace 呈现
        self.last_error = Some(E_STATE.into());
        Err(format!("{}:{}@{}", E_STATE, tool, self.status))
    }

    /// 补遗导入：content_version +1（TC-09 级联骨架口径）
    pub fn bump_content_version(&mut self) {
        self.content_version += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guard_rejects_out_of_order() {
        let mut m = Machine::new();
        m.create_project("X");
        assert_eq!(m.status, "DRAFT");
        // 未导入即起草 → E_STATE
        assert!(m.call_tool("draft_response_section").is_err());
        assert_eq!(m.status, "DRAFT"); // 零副作用
        m.call_tool("import_tender_files").unwrap();
        m.call_tool("extract_requirements").unwrap();
        assert_eq!(m.status, "REQUIREMENTS_EXTRACTED");
        // 起草仍越级（需 M3 的 OUTLINE_APPROVED）→ E_STATE
        assert!(m.call_tool("draft_response_section").is_err());
        assert_eq!(m.status, "REQUIREMENTS_EXTRACTED");
    }

    #[test]
    fn file_idempotency() {
        let mut m = Machine::new();
        assert!(m.import_file("abc", "main", "a.docx").is_some());
        assert!(m.import_file("abc", "main", "a.docx").is_none());
    }
}
