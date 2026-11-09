//! docx.rs — DOCX 解析（zip + quick-xml 拉取式解析 word/document.xml）
//!
//! 输出块（含确定性 locator）：
//!   - Heading1/Heading2 → Heading 块（章节上下文推进）
//!   - 普通段落 → Para 块
//!   - 表格 → TableRow（单元格 \t 连接）+ TableCell（非空单元格）块
//! 页码按 w:br type="page" 分页符估算（docx 无固定分页——口径记录于 m1/README）。

use crate::contract::Block;
use quick_xml::events::Event;
use quick_xml::Reader;
use std::io::Read;
use std::path::Path;

pub fn parse(path: &Path, file_name: &str, order_start: u32) -> Result<Vec<Block>, String> {
    let file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    let mut zf = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
    let mut xml = Vec::new();
    zf.by_name("word/document.xml")
        .map_err(|e| format!("no document.xml: {}", e))?
        .read_to_end(&mut xml)
        .map_err(|e| e.to_string())?;

    let mut reader = Reader::from_reader(xml.as_slice());
    reader.config_mut().trim_text(false);
    let mut blocks: Vec<Block> = Vec::new();
    let mut order = order_start;

    // 上下文
    let mut h1 = String::new();
    let mut h2 = String::new();
    let mut page: u32 = 1;
    let mut para_idx: u32 = 0;

    // 段落/表格状态机
    #[derive(PartialEq)]
    enum S { Body, Para, Cell, TableMeta }
    let mut state = S::Body;
    let mut p_style: String = String::new();
    let mut p_text = String::new();
    let mut in_text = false;
    // 表格
    let mut table_idx: u32 = 0;
    let mut _row_idx: u32 = 0; // 行计数仅调试用；行定位由 table_loc+enumerate 承担
    let mut row_cells: Vec<String> = Vec::new();
    let mut cell_text = String::new();
    let mut table_rows: Vec<Vec<String>> = Vec::new();
    let mut table_loc = String::new();

    fn local(e: &quick_xml::events::BytesStart) -> String {
        let q = e.name();
        let full: &[u8] = q.as_ref();
        let local_bytes = match full.iter().position(|&b| b == b':') {
            Some(i) => &full[i + 1..],
            None => full,
        };
        String::from_utf8_lossy(local_bytes).to_string()
    }

    fn local_end(e: &quick_xml::events::BytesEnd) -> String {
        let q = e.name();
        let full: &[u8] = q.as_ref();
        let local_bytes = match full.iter().position(|&b| b == b':') {
            Some(i) => &full[i + 1..],
            None => full,
        };
        String::from_utf8_lossy(local_bytes).to_string()
    }

    loop {
        match reader.read_event() {
            Ok(Event::Start(e)) => {
                let name = local(&e);
                match name.as_str() {
                    "p" if state == S::Body => {
                        state = S::Para;
                        p_style.clear();
                        p_text.clear();
                    }
                    "p" if state == S::Cell => {
                        state = S::Cell; // 嵌套段落：并入单元格文本（空格连接）
                        if !cell_text.is_empty() { cell_text.push(' '); }
                    }
                    "pStyle" if state == S::Para || state == S::Cell => {
                        if let Ok(Some(v)) = e.try_get_attribute("w:val") {
                            let s = String::from_utf8_lossy(v.value.as_ref()).to_string();
                            if state == S::Para { p_style = s; }
                        }
                    }
                    "t" => { in_text = true; }
                    "br" => {
                        if let Ok(Some(v)) = e.try_get_attribute("w:type") {
                            if v.value.as_ref() == b"page" { page += 1; }
                        }
                    }
                    "tbl" => {
                        state = S::TableMeta;
                        table_idx += 1;
                        _row_idx = 0;
                        table_rows.clear();
                        table_loc = format!("{} > {} 表{}", if h1.is_empty() {"#root".into()} else {h1.clone()},
                                            if h2.is_empty() {"-".into()} else {h2.clone()}, table_idx);
                    }
                    "tr" => { _row_idx += 1; row_cells.clear(); }
                    "tc" => {
                        state = S::Cell;
                        cell_text.clear();
                    }
                    _ => {}
                }
            }
            Ok(Event::Empty(e)) => {
                let name = local(&e);
                match name.as_str() {
                    "br" => {
                        if let Ok(Some(v)) = e.try_get_attribute("w:type") {
                            if v.value.as_ref() == b"page" && state != S::Cell { page += 1; }
                        }
                    }
                    // pStyle 常为自闭合空元素 <w:pStyle w:val="Heading1"/>
                    "pStyle" if state == S::Para => {
                        if let Ok(Some(v)) = e.try_get_attribute("w:val") {
                            p_style = String::from_utf8_lossy(v.value.as_ref()).to_string();
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::Text(t)) => {
                if in_text {
                    let s = t.unescape().map_err(|e| e.to_string())?;
                    match state {
                        S::Para => p_text.push_str(&s),
                        S::Cell => cell_text.push_str(&s),
                        _ => {}
                    }
                }
            }
            Ok(Event::End(e)) => {
                let name = local_end(&e);
                match name.as_str() {
                    "t" => { in_text = false; }
                    "p" if state == S::Para => {
                        state = S::Body;
                        para_idx += 1;
                        let text = p_text.trim();
                        if !text.is_empty() {
                            let kind = if p_style.starts_with("Heading1") { "Heading1" }
                                else if p_style.starts_with("Heading2") { "Heading2" }
                                else { "Para" };
                            let locator = format!("{} > {} #p{}", 
                                if h1.is_empty() {"#root".into()} else {h1.clone()},
                                if h2.is_empty() {"-".into()} else {h2.clone()}, para_idx);
                            if kind == "Heading1" {
                                h1 = text.to_string();
                                h2.clear();
                            } else if kind == "Heading2" {
                                h2 = text.to_string();
                            }
                            blocks.push(Block {
                                file: file_name.into(), kind: kind.into(), locator,
                                page, text: text.to_string(), order,
                            });
                            order += 1;
                        }
                    }
                    "p" if state == S::Cell => { /* 单元格内段落已并入 */ }
                    "tc" if state == S::Cell => {
                        state = S::TableMeta;
                        row_cells.push(cell_text.trim().to_string());
                    }
                    "tr" => {
                        table_rows.push(row_cells.clone());
                    }
                    "tbl" => {
                        state = S::Body;
                        // 发块：先 Row（\t 连接），后各非空 Cell
                        for (ri, cells) in table_rows.iter().enumerate() {
                            let joined = cells.join("\t");
                            if !joined.trim().is_empty() {
                                blocks.push(Block {
                                    file: file_name.into(), kind: "TableRow".into(),
                                    locator: format!("{} 行{}", table_loc, ri + 1),
                                    page, text: joined, order,
                                });
                                order += 1;
                            }
                            for (ci, c) in cells.iter().enumerate() {
                                if !c.trim().is_empty() {
                                    blocks.push(Block {
                                        file: file_name.into(), kind: "TableCell".into(),
                                        locator: format!("{} 行{} 列{}", table_loc, ri + 1, ci + 1),
                                        page, text: c.clone(), order,
                                    });
                                    order += 1;
                                }
                            }
                        }
                        table_rows.clear();
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(e) => return Err(format!("xml: {}", e)),
        }
    }
    Ok(blocks)
}
