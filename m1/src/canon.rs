//! canon.rs — OCR 文本确定性规整（扫描件通道专用，文本层通道不适用）
//!
//! 背景（v0.4 实测）：tesseract chi_sim 对 B2 扫描件的系统性混淆类——
//!   ① 全角标点 → 半角（；→; ，→, （→( ：→:）；
//!   ② CJK 字符间插入伪空格；
//!   ③ CJK 邻接的 "." 存在两类真值（"·" 间隔号 / "1." 编号），不可盲映射。
//! 处理（确定性、逐字符、可文档化）：
//!   - CJK 邻接环境下把 ; , : ( ) ? ! 回正为全角（对应源像素中的全角标点）；
//!   - "." 仅在**两侧均为汉字**时回正为间隔号 "·"（"页.盖"→"页·盖"；"1.我"不动）；
//!   - 删除任一侧为 CJK 的空格（源图像无空格——OCR 行切分伪影）。
//! 判分对齐器（grade.py）要求锚点摘录**逐字包含**，因此必须向 GT 书写习惯（全角）回正。

pub fn is_han(c: char) -> bool {
    matches!(c as u32, 0x4E00..=0x9FFF)
}

/// CJK 邻接域：汉字 / CJK 标点 / 全角形式（OCR 混淆发生的环境）
fn is_cjk_zone(c: char) -> bool {
    matches!(c as u32,
        0x4E00..=0x9FFF        // 汉字
        | 0x3000..=0x303F      // CJK 标点（。、「」等）
        | 0xFF00..=0xFFEF      // 全角形式（ＡＢＣ，（）等）
        | 0x2010..=0x2027      // 连字符/省略/引号族（＿—“”等常伴）
        | 0x00B7)              // 间隔号
}

/// OCR 行规整：半角标点全角回正 + CJK 邻接空格删除。
/// 逐字符基于**原文**邻域判定（不用增量结果），保证确定性。
pub fn canon_ocr_line(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let n = chars.len();
    let mut out = String::with_capacity(s.len() + 8);
    for i in 0..n {
        let c = chars[i];
        let left = if i > 0 { chars[i - 1] } else { '\0' };
        let right = if i + 1 < n { chars[i + 1] } else { '\0' };
        match c {
            ';' | ',' | ':' | '(' | ')' | '?' | '!' => {
                if is_cjk_zone(left) || is_cjk_zone(right) {
                    out.push(match c {
                        ';' => '；', ',' => '，', ':' => '：',
                        '(' => '（', ')' => '）', '?' => '？', _ => '！',
                    });
                } else {
                    out.push(c);
                }
            }
            '.' => {
                // 两侧均汉字 → 间隔号（源像素常见"页·盖章"式书写）；其余（编号"1." 等）不动
                if is_han(left) && is_han(right) {
                    out.push('·');
                } else {
                    out.push(c);
                }
            }
            ' ' => {
                if is_cjk_zone(left) || is_cjk_zone(right) {
                    // 空格为 OCR 伪影，删除
                } else {
                    out.push(c);
                }
            }
            _ => out.push(c),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clause_verbatim_restored() {
        let ocr = "本页为投标函标准格式样例; 未按本样例格式签署并加盖单位公章的投标文件，作否决投标处理";
        let want = "本页为投标函标准格式样例；未按本样例格式签署并加盖单位公章的投标文件，作否决投标处理";
        assert_eq!(canon_ocr_line(ocr), want);
    }

    #[test]
    fn numbering_dot_preserved() {
        assert_eq!(canon_ocr_line("1. 我方考察研究了上述项目的招标文件全册"), "1.我方考察研究了上述项目的招标文件全册");
    }

    #[test]
    fn middle_dot_restored() {
        assert_eq!(canon_ocr_line("(格式样例页.盖章扫描件)"), "（格式样例页·盖章扫描件）");
    }
}
