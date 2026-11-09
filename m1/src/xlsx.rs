//! xlsx.rs — XLSX 解析（zip + quick-xml：sharedStrings + sheet1）
//!
//! 输出：每非空行一个 XlsxRow 块（单元格 \t 连接，跳过全空行）。

use crate::contract::Block;
use quick_xml::events::Event;
use quick_xml::Reader;
use std::io::Read;
use std::path::Path;

fn local_start(e: &quick_xml::events::BytesStart) -> String {
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

pub fn parse(path: &Path, file_name: &str, order_start: u32) -> Result<Vec<Block>, String> {
    let file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    let mut zf = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;

    // ---- sharedStrings：按 <si> 收集（<t> 全部拼接；富文本 <r> 同样处理）----
    let mut shared: Vec<String> = Vec::new();
    if let Ok(mut f) = zf.by_name("xl/sharedStrings.xml") {
        let mut xml = Vec::new();
        f.read_to_end(&mut xml).map_err(|e| e.to_string())?;
        let mut r = Reader::from_reader(xml.as_slice());
        r.config_mut().trim_text(true);
        let mut cur = String::new();
        let mut in_t = false;
        loop {
            match r.read_event() {
                Ok(Event::Start(e)) => {
                    if local_start(&e) == "t" { in_t = true; }
                }
                Ok(Event::Text(t)) => {
                    if in_t {
                        cur.push_str(&t.unescape().map_err(|e| e.to_string())?);
                    }
                }
                Ok(Event::End(e)) => {
                    let n = local_end(&e);
                    if n == "t" { in_t = false; }
                    if n == "si" {
                        shared.push(cur.clone());
                        cur.clear();
                    }
                }
                Ok(Event::Eof) => break,
                Ok(_) => {}
                Err(e) => return Err(format!("sharedStrings: {}", e)),
            }
        }
    }

    // ---- sheet1：行 → XlsxRow 块 ----
    let mut xml = Vec::new();
    zf.by_name("xl/worksheets/sheet1.xml")
        .map_err(|e| format!("no sheet1: {}", e))?
        .read_to_end(&mut xml)
        .map_err(|e| e.to_string())?;
    let mut r = Reader::from_reader(xml.as_slice());
    r.config_mut().trim_text(false);

    let mut blocks = Vec::new();
    let mut order = order_start;
    let mut row_idx: u32 = 0;
    let mut cells: Vec<String> = Vec::new();
    let mut cell_buf = String::new();
    let mut cell_type = String::new();
    let mut in_v = false;
    let mut in_c = false;
    let mut in_is = false;
    let mut in_t_inline = false;

    loop {
        match r.read_event() {
            Ok(Event::Start(e)) => {
                match local_start(&e).as_str() {
                    "row" => { row_idx += 1; cells.clear(); }
                    "c" => {
                        in_c = true;
                        cell_buf.clear();
                        cell_type.clear();
                        if let Ok(Some(t)) = e.try_get_attribute("t") {
                            cell_type = String::from_utf8_lossy(t.value.as_ref()).to_string();
                        }
                    }
                    "v" => { in_v = true; }
                    "is" if in_c => { in_is = true; }
                    "t" if in_c && in_is => { in_t_inline = true; }
                    _ => {}
                }
            }
            Ok(Event::Empty(_)) => {}
            Ok(Event::Text(t)) => {
                if in_v || in_t_inline {
                    cell_buf.push_str(&t.unescape().map_err(|e| e.to_string())?);
                }
            }
            Ok(Event::End(e)) => {
                match local_end(&e).as_str() {
                    "v" => { in_v = false; }
                    "t" if in_c => { in_t_inline = false; }
                    "is" => { in_is = false; }
                    "c" => {
                        in_c = false;
                        let val = if cell_type == "s" {
                            let idx: usize = cell_buf.trim().parse().unwrap_or(usize::MAX);
                            shared.get(idx).cloned().unwrap_or_default()
                        } else {
                            cell_buf.trim().to_string()
                        };
                        cells.push(val);
                    }
                    "row" => {
                        let joined = cells.join("\t");
                        if !joined.trim().is_empty() {
                            blocks.push(Block {
                                file: file_name.into(),
                                kind: "XlsxRow".into(),
                                locator: format!("sheet1 行{}", row_idx),
                                page: 1,
                                text: joined,
                                order,
                            });
                            order += 1;
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(e) => return Err(format!("sheet1: {}", e)),
        }
    }
    Ok(blocks)
}
