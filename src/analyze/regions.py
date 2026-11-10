"""区域层级解析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R51：原始 ``region`` 字段口径混杂（「浙江省」「浙江省杭州市」
「杭州」「浙江省杭州市西湖区」并存），直接聚合并排会把同一省
拆成多行。本模块提供**省级归一视图**：

- 34 个省级行政区全名识别（23 省 + 5 自治区 + 4 直辖市 +
  2 特别行政区），前缀匹配容忍全/简称差（「浙江」→「浙江省」）；
- 直辖市（北京/上海/天津/重庆）市 = 省，不再重复计行；
- 市级抽取：省级段后的首个 ``XX市``；县级及以下**丢弃**
  （省级视图不需要，保留反而泄露细粒度噪声）；
- 解析不出 → ``None``（调用方归 ``未知``，不猜数）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.analyze.dataset import AnalysisDataset

#: 省级行政区规范名（含后缀），顺序即表意优先序。
_PROVINCES: tuple = (
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "海南省",
    "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省",
    "内蒙古自治区", "广西壮族自治区", "西藏自治区",
    "宁夏回族自治区", "新疆维吾尔自治区",
    "香港特别行政区", "澳门特别行政区", "台湾省",
)

#: 简称 → 规范名（前缀匹配兜底用）。
_PROVINCE_ALIASES: Dict[str, str] = {
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区",
}
# 通用短名：去「省/市」后缀（浙江省→浙江、上海市→上海……）
for _name in _PROVINCES:
    if _name.endswith("省") or _name.endswith("市"):
        _PROVINCE_ALIASES.setdefault(_name[:-1], _name)

#: 直辖市——市级视图与省级同位。
_MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}

#: 已规范省名集合（快速查）。
_PROVINCE_SET = frozenset(_PROVINCES)


def parse_region(region: str) -> Optional[Dict[str, str]]:
    """解析区域字符串为省/市两级。

    Args:
        region: 原始区域文本（可含省市县任意混杂）。

    Returns:
        ``{"province": "浙江省", "city": "杭州市"}`` 形态；
        市缺失为 ``None``；完全解析不出返回 ``None``
        （调用方归 ``未知``）。

    Examples::

        >>> parse_region("浙江省杭州市") == {"province": "浙江省", "city": "杭州市"}
        True
        >>> parse_region("浙江省") == {"province": "浙江省", "city": None}
        True
        >>> parse_region("北京市海淀区")["city"]
        '北京市'
        >>> parse_region("杭州") is None  # 裸市名无法定位省——不猜数
        True
    """
    text = (region or "").strip()
    if not text:
        return None

    province: Optional[str] = None
    rest = text
    for name in _PROVINCES:
        if text.startswith(name):
            province = name
            rest = text[len(name):]
            break
    if province is None:
        # 简称兜底（自治区/特别行政区常用简称）
        for alias, canonical in _PROVINCE_ALIASES.items():
            if text.startswith(alias):
                province = canonical
                rest = text[len(alias):]
                break
    if province is None:
        # 裸市名（「杭州市」）无法定位省——不猜数
        return None

    city: Optional[str] = None
    # 市级 = 省段后首个「XX市」
    idx = rest.find("市")
    if idx > 0:
        candidate = rest[: idx + 1]
        # 剥可能的自治区/省残段（如「浙江省宁夏市」异常输入不常见，宽容处理）
        candidate = candidate.lstrip("省壮族自治区维吾尔回族")
        if candidate.endswith("市") and len(candidate) > 1:
            city = candidate
    if province in _MUNICIPALITIES:
        city = province  # 直辖市市=省

    return {"province": province, "city": city}


def province_distribution(
    dataset: AnalysisDataset,
) -> Dict[str, Any]:
    """省级归一分布（R51）。

    Returns:
        ``{"distribution": {省: 条数}, "parsed_count": 解析成功数,
        "unknown_count": 解析失败数}``——分布按条数降序、并列按省名，
        解析失败如实计数（不猜数）。
    """
    counter: Dict[str, int] = {}
    parsed = 0
    unknown = 0
    for record in dataset.records:
        region = (record.get("region") or "").strip()
        if not region:
            unknown += 1
            continue
        parsed_region = parse_region(region)
        if parsed_region is None:
            unknown += 1
            continue
        parsed += 1
        counter[parsed_region["province"]] = (
            counter.get(parsed_region["province"], 0) + 1
        )
    distribution = dict(
        sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    return {
        "distribution": distribution,
        "parsed_count": parsed,
        "unknown_count": unknown,
    }
