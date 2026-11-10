"""templates --show 渲染面测试（#601 R69）。"""

import pytest

import main as main_mod


class TestTemplatesShow:
    def test_show_renders_with_sample(self, capsys):
        rc = main_mod.main(["templates", "--show", "bid_extraction"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "抽取结构化信息" in out
        assert "300万元" in out  # 样例数据真的进了提示词
        assert "JSON" in out

    def test_show_all_templates_renderable(self, capsys):
        for name in (
            "bid_extraction", "bid_analysis",
            "competitor_analysis", "report_generation",
        ):
            capsys.readouterr()
            rc = main_mod.main(["templates", "--show", name])
            assert rc == 0, name
            assert capsys.readouterr().out.strip()

    def test_unknown_name_actionable_error(self, capsys):
        rc = main_mod.main(["templates", "--show", "不存在模板"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "模板不存在" in err
        assert "bid_extraction" in err  # 可用名单一并给出

    def test_list_mode_still_works_with_hint(self, capsys):
        rc = main_mod.main(["templates"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "可用提示词模板" in out
        assert "--show" in out  # 新能力可发现

    def test_direct_call_backward_compatible(self, capsys):
        """run_templates() 无参直调（旧 API）仍可用。"""
        assert main_mod.run_templates() == 0
        assert "可用提示词模板" in capsys.readouterr().out
