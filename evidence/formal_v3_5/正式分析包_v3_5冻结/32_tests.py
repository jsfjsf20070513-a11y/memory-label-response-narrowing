#!/usr/bin/env python3
"""不调用模型的冻结算法单测与合成反例。"""

from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jsonschema

import analysis_v2 as a
import core as c
import pipeline as p


HERE = Path(__file__).resolve().parent
FIXTURE = json.loads((HERE / "fixtures" / "algorithm_cases.json").read_text(encoding="utf-8"))


class TestFrozenMath(unittest.TestCase):
    def test_sign_cases(self):
        for row in FIXTURE["sign_cases"]:
            self.assertAlmostEqual(c.exact_sign_p(row["n"], row["k"]), row["p"])

    def test_method_score(self):
        self.assertEqual(c.method_score("B", "C", "B", "C"), 1)
        self.assertEqual(c.method_score("C", "B", "B", "C"), -1)
        self.assertEqual(c.method_score("B", "B", "B", "C"), 0)

    def test_blind_pair(self):
        pair, focal, reference = c.blind_pair(FIXTURE["blind_mapping"], "M", "N")
        self.assertEqual((pair, focal, reference), ("B_vs_C", "B", "C"))

    def test_fixed_sequence(self):
        for row in FIXTURE["fixed_sequence_cases"]:
            got = c.fixed_sequence(row["primary"], row["secondary"])
            self.assertEqual(got["secondary_inferentially_tested"], row["secondary_tested"])
            self.assertEqual(got["specificity_supported"], row["specificity"])

    def test_length_alarm(self):
        self.assertTrue(c.length_entanglement_alarm(69, 100, 4, 1, 0.30))
        self.assertFalse(c.length_entanglement_alarm(70, 100, 4, 1, 0.30))
        self.assertFalse(c.length_entanglement_alarm(60, 100, 1, 2, 0.30))

    def test_sign_summary_requires_six_total_positive(self):
        five = p.sign_summary([{"consensus": 1}] * 5 + [{"consensus": 0}] * 7, 6)
        self.assertAlmostEqual(five["one_sided_exact_p"], 0.03125)
        self.assertFalse(five["pass"])
        six = p.sign_summary([{"consensus": 1}] * 6 + [{"consensus": 0}] * 6, 6)
        self.assertTrue(six["pass"])


class TestCrossFamilyVote(unittest.TestCase):
    def test_fixture_cases(self):
        for row in FIXTURE["group_vote_cases"]:
            got = c.group_vote(row["votes"])
            self.assertEqual(got["status"], row["expected_status"], row["name"])
            self.assertEqual(got["result"], row["expected_result"], row["name"])

    def test_three_distinct_is_no_majority(self):
        got = c.group_vote({"M1": "A", "M2": "B", "M3": "C"})
        self.assertEqual(got["status"], "no_majority")

    def test_two_to_one_keeps_minority_flag(self):
        got = c.group_vote({"M1": "A", "M2": "B", "M3": "A"})
        self.assertEqual(got["result"], "A")
        self.assertTrue(got["minority_flag"])


class TestEvidenceLocation(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(c.locate_evidence("甲乙甲", "甲", 2)["mode"], "exact")

    def test_markdown_only_normalization(self):
        got = c.locate_evidence("这是**关键**证据", "这是关键证据", 1)
        self.assertEqual(got["mode"], "remove_markdown_emphasis")
        self.assertEqual((got["original_start"], got["original_end"]), (0, 10))
        self.assertEqual((got["normalized_start"], got["normalized_end"]), (0, 6))

    def test_no_punctuation_repair(self):
        self.assertIsNone(c.locate_evidence("甲，乙", "甲乙", 1))

    def test_unpaired_emphasis_marker_is_not_removed(self):
        self.assertIsNone(c.locate_evidence("甲**乙", "甲乙", 1))


class TestEvidenceDowngrade(unittest.TestCase):
    def test_review_cases(self):
        block = {
            "block_id": "S2-B01",
            "comparisons": {
                "A_vs_B": {
                    "math_focus": {
                        "choice": "A",
                        "decisive": {"answer": "A", "evidence": "数学证据", "occurrence": 1},
                        "reason": "x",
                    },
                    "nonmath_breadth": {"choice": "相当", "decisive": None, "reason": "x"},
                }
            },
        }
        answer_texts = {"A": "数学证据", "B": "其他", "C": "其他"}
        task = p.ticket_id("M1", "S2", "S2-B01", "A_vs_B", "math_focus")
        for row in FIXTURE["evidence_review_cases"]:
            reviews = {(reviewer, task): value for reviewer, value in row["judgments"].items()}
            got, _ = p.adjusted_choice(
                "M1", "S2", block, "A_vs_B", "math_focus", reviews, answer_texts
            )
            self.assertEqual(got, row["expected"], row["name"])

    def test_unlocatable_decisive_evidence_is_downgraded_before_review(self):
        block = {
            "block_id": "S2-B01",
            "comparisons": {"A_vs_B": {"math_focus": {
                "choice": "A",
                "decisive": {"answer": "A", "evidence": "不存在", "occurrence": 1},
                "reason": "x",
            }}},
        }
        got, meta = p.adjusted_choice(
            "M1", "S2", block, "A_vs_B", "math_focus", {},
            {"A": "原文", "B": "其他", "C": "其他"},
        )
        self.assertEqual(got, "无法判断")
        self.assertEqual(meta["review"], "evidence_location_failed")


def synthetic_menu_doc():
    menu = c.menu_definitions()
    answers = {
        "S2-B01": {
            "A": "可以比较修理成本，也考虑旧物承载的回忆。",
            "B": "可以考虑丢弃的环境影响和家庭共同记忆。",
            "C": "先确认它还能不能恢复功能。",
        }
    }
    specs = {
        "A": ("S2-D2", "修理成本", "数学"),
        "B": ("S2-D4", "环境影响", "非数学"),
        "C": ("S2-D1", "恢复功能", "非数学"),
    }
    coded_answers = {}
    for label, (mid, evidence, tag) in specs.items():
        coded_answers[label] = {
            "directions": [{
                "definition": menu[mid][1], "evidence": evidence, "from_menu": True,
                "local_id": "d1", "menu_id": mid, "name": menu[mid][0],
                "occurrence": 1, "tag": tag,
            }],
            "identity_evidence": None,
            "identity_explicit": False,
        }
    equal = {"choice": "相当", "decisive": None, "reason": "没有可靠差异"}
    doc = {
        "blocks": [{
            "answers": coded_answers,
            "block_id": "S2-B01",
            "comparisons": {
                "A_vs_B": {"math_focus": copy.deepcopy(equal), "nonmath_breadth": copy.deepcopy(equal)},
                "A_vs_C": {"math_focus": copy.deepcopy(equal), "nonmath_breadth": copy.deepcopy(equal)},
                "B_vs_C": {"math_focus": copy.deepcopy(equal), "nonmath_breadth": copy.deepcopy(equal)},
            },
        }],
        "method": "menu",
        "question": "S2",
        "slot": "M1",
    }
    return doc, answers


class TestCodingSemantics(unittest.TestCase):
    def test_valid_synthetic_menu_doc(self):
        doc, answers = synthetic_menu_doc()
        schema = c.load(HERE / "12_schema_coding_menu.json")
        jsonschema.validate(doc, schema)
        self.assertEqual(c.validate_coding(doc, "M1", "S2", answers), [])

    def test_wrong_question_menu_id_is_blocked(self):
        doc, answers = synthetic_menu_doc()
        doc["blocks"][0]["answers"]["A"]["directions"][0]["menu_id"] = "S8-D1"
        errors = c.validate_coding(doc, "M1", "S2", answers)
        self.assertTrue(any("不属于当前题" in error for error in errors))

    def test_unlocatable_evidence_is_blocked(self):
        doc, answers = synthetic_menu_doc()
        doc["blocks"][0]["answers"]["A"]["directions"][0]["evidence"] = "并不存在"
        errors = c.validate_coding(doc, "M1", "S2", answers)
        self.assertTrue(any("无法定位" in error for error in errors))

    def test_directional_verdict_must_copy_registered_direction(self):
        doc, answers = synthetic_menu_doc()
        d = doc["blocks"][0]["answers"]["A"]["directions"][0]
        doc["blocks"][0]["comparisons"]["A_vs_B"]["math_focus"] = {
            "choice": "A",
            "decisive": {
                "answer": "A", "definition": d["definition"], "evidence": d["evidence"],
                "local_id": "d1", "name": "被改写的名称", "occurrence": 1,
            },
            "reason": "A 更数学",
        }
        schema = c.load(HERE / "12_schema_coding_menu.json")
        jsonschema.validate(doc, schema)
        errors = c.validate_coding(doc, "M1", "S2", answers)
        self.assertTrue(any("未逐字复制方向" in error for error in errors))

    def test_math_verdict_cannot_use_nonmath_direction(self):
        doc, answers = synthetic_menu_doc()
        d = doc["blocks"][0]["answers"]["A"]["directions"][0]
        d["tag"] = "非数学"
        doc["blocks"][0]["comparisons"]["A_vs_B"]["math_focus"] = {
            "choice": "A",
            "decisive": {
                "answer": "A", "definition": d["definition"], "evidence": d["evidence"],
                "local_id": "d1", "name": d["name"], "occurrence": 1,
            },
            "reason": "A 更数学",
        }
        errors = c.validate_coding(doc, "M1", "S2", answers)
        self.assertTrue(any("方向标签必须为 数学" in error for error in errors))

    def test_duplicate_menu_direction_is_blocked(self):
        doc, answers = synthetic_menu_doc()
        duplicate = copy.deepcopy(doc["blocks"][0]["answers"]["A"]["directions"][0])
        duplicate["local_id"] = "d2"
        doc["blocks"][0]["answers"]["A"]["directions"].append(duplicate)
        errors = c.validate_coding(doc, "M1", "S2", answers)
        self.assertTrue(any("菜单方向重复" in error for error in errors))

    def test_unlocatable_decisive_direction_is_accepted_for_later_downgrade(self):
        doc, answers = synthetic_menu_doc()
        d = doc["blocks"][0]["answers"]["A"]["directions"][0]
        d["evidence"] = "并不存在"
        doc["blocks"][0]["comparisons"]["A_vs_B"]["math_focus"] = {
            "choice": "A",
            "decisive": {
                "answer": "A", "definition": d["definition"], "evidence": d["evidence"],
                "local_id": d["local_id"], "name": d["name"], "occurrence": 1,
            },
            "reason": "A 更数学",
        }
        errors = c.validate_coding(doc, "M1", "S2", answers)
        self.assertFalse(any("证据无法定位" in error for error in errors))


class TestSentinel(unittest.TestCase):
    def build_docs(self):
        task_specs = c.load(HERE / "05_sentinel_tasks.json")["tasks"]
        mapping = {"equal": "相当", "cannot": "无法判断", "A": "A", "B": "B"}
        docs = {}
        for slot in c.CONFIG["coding_slots"]:
            docs[slot] = {
                "slot": slot,
                "items": [{
                    "task_id": task["task_id"],
                    "math_focus": mapping[task["expected"]["math_focus"]],
                    "nonmath_breadth": mapping[task["expected"]["nonmath_breadth"]],
                    "reason": "合成金标准",
                } for task in task_specs],
            }
        return docs

    def test_gold_passes(self):
        self.assertEqual(p.sentinel_report(self.build_docs())["status"], "PASS")

    def test_two_claude_cannot_hide_codex_error(self):
        docs = self.build_docs()
        item = next(row for row in docs["M3"]["items"] if row["task_id"] == "T5")
        item["math_focus"] = "B"
        self.assertEqual(p.sentinel_report(docs)["status"], "FAIL")


class TestRandomization(unittest.TestCase):
    def test_generation_balance_and_interleaving(self):
        rows = c.RANDOM_TABLE["generation_order"]
        self.assertEqual(len(rows), 48)
        self.assertEqual({arm: sum(row["arm"] == arm for row in rows) for arm in "NGM"},
                         {"N": 16, "G": 16, "M": 16})
        arms = [row["arm"] for row in rows]
        self.assertFalse(any(arms[i] == arms[i+1] == arms[i+2] for i in range(46)))
        self.assertFalse(any(len(set(arms[i:i+6])) < 3 for i in range(43)))

    def test_all_blocks_have_three_arms(self):
        seen = {}
        for row in c.RANDOM_TABLE["generation_order"]:
            seen.setdefault(row["block_id"], set()).add(row["arm"])
        self.assertEqual(len(seen), 16)
        self.assertTrue(all(arms == {"N", "G", "M"} for arms in seen.values()))

    def test_blind_positions_are_near_balanced(self):
        counts = {
            label: {
                arm: sum(mapping[label] == arm for mapping in c.RANDOM_TABLE["blind_mapping"].values())
                for arm in ("N", "G", "M")
            }
            for label in c.LABELS
        }
        self.assertTrue(all(value in (5, 6) for row in counts.values() for value in row.values()))


class TestPackageInputs(unittest.TestCase):
    def test_v35_is_quota_resume_only_with_separate_authorization(self):
        self.assertEqual(c.RUN_DIR.name, "正式分析运行_v3_5")
        self.assertEqual(c.SOURCE_RUN_DIR.name, "正式运行_v1_1")
        self.assertEqual(c.AUTH_FILENAME, "00_open_analysis_v3_5.json")
        self.assertEqual(c.AUTH_SCOPE, "formal_analysis_v3_5_quota_resume_up_to_23_calls")
        verify = (HERE / "99_verify.sh").read_text(encoding="utf-8")
        self.assertIn("../正式分析运行_v3_5/00_open_analysis_v3_5.json", verify)
        self.assertIn("51_build_review_schemas.py", verify)
        source = (HERE / "analysis_v2.py").read_text(encoding="utf-8")
        self.assertIn('choices=("prepare", "review", "aggregate")', source)

    def test_transport_prompt_removes_repeated_menu_copying(self):
        template = (HERE / "23_prompt_transport_menu.md").read_text(encoding="utf-8")
        self.assertIn("菜单内方向只填写 `menu_id`", template)
        self.assertIn("`name=null`、`definition=null`", template)
        self.assertIn("只填胜方 `answer` 和该胜方已登记方向的 `local_id`", template)
        self.assertIn("不得为菜单", template)
        self.assertIn("两边都没有该类方向", template)
        self.assertIn("仍属于“成本时间”方向", template)
        self.assertIn("即使写在同一句里也必须拆开", template)
        self.assertIn("`menu_id` **最多登记一次**", template)
        self.assertIn("最小", (HERE / "24_prompt_transport_open.md").read_text(encoding="utf-8"))

    def test_parent_v3_failure_and_reused_m1_m2_are_reproducible(self):
        a.verify_parent_v3_failure()

    def test_v31_pre_inference_schema_rejection_is_reproducible(self):
        a.verify_v31_transport_rejection()

    def test_v32_completed_coding_and_review_failure_are_reproducible(self):
        a.verify_v32_completed_coding_and_review_failure()

    def test_v33_historical_call_budget_is_recorded(self):
        cfg = c.CONFIG["analysis_v3_3"]
        total = cfg["review_calls"] + cfg["retry_allowance"]
        self.assertEqual(total, 38)
        self.assertEqual(cfg["review_chunk_size"], 30)
        self.assertEqual(cfg["inherited_coding_slots"], ["M1", "M2", "M3", "O1", "O2", "O3"])

    def test_v33_m1_review_and_m2_failure_are_reproducible(self):
        a.verify_v33_m1_review_and_m2_failure()

    def test_v34_historical_call_budget_is_recorded(self):
        cfg = c.CONFIG["analysis_v3_4"]
        total = cfg["review_calls"] + cfg["retry_allowance"]
        self.assertEqual(total, 33)
        self.assertEqual(cfg["reused_review_slots"], ["M1"])
        self.assertEqual(cfg["new_review_slots"], ["M2", "M3", "O1", "O2", "O3"])

    def test_v34_completed_reviews_and_quota_failure_are_reproducible(self):
        a.verify_v34_completed_reviews_and_quota_failure()

    def test_v35_call_budget_is_exact(self):
        cfg = c.CONFIG["analysis_v3_5"]
        total = cfg["review_calls"] + cfg["retry_allowance"]
        self.assertEqual(total, 23)
        self.assertEqual(total, c.CONFIG["thresholds"]["max_requests_for_completed_run"])
        self.assertEqual(cfg["reused_review_slots"], ["M1", "M2", "M3"])
        self.assertEqual(cfg["new_review_slots"], ["O1", "O2", "O3"])

    def test_v33_review_plan_is_exactly_thirty_calls(self):
        codings = a.load_v32_codings()
        blinded = c.load(a.V32_RUN / "answers_blinded.json")
        expected_tasks = {"M1": 144, "M2": 143, "M3": 133, "O1": 146, "O2": 145, "O3": 133}
        call_counts = {}
        for slot in sorted(c.CONFIG["coding_slots"]):
            tasks = p.review_tasks_for(slot, codings, blinded)
            chunks = a.review_chunks(tasks)
            self.assertEqual(len(tasks), expected_tasks[slot])
            self.assertTrue(all(1 <= len(chunk) <= 30 for chunk in chunks))
            self.assertEqual([item["task_id"] for chunk in chunks for item in chunk], [item["task_id"] for item in tasks])
            call_counts[slot] = len(chunks)
        self.assertEqual(call_counts, {slot: 5 for slot in expected_tasks})
        self.assertEqual(sum(call_counts.values()), c.CONFIG["analysis_v3_3"]["review_calls"])

    def test_v34_keyed_review_plan_is_exactly_twenty_five_calls(self):
        codings = a.load_v32_codings()
        blinded = c.load(a.V32_RUN / "answers_blinded.json")
        total = 0
        for slot in c.CONFIG["analysis_v3_4"]["new_review_slots"]:
            tasks = p.review_tasks_for(slot, codings, blinded)
            chunks = a.review_chunks(tasks)
            self.assertEqual(len(chunks), 5)
            for index, chunk in enumerate(chunks, 1):
                schema_path = a.keyed_schema_path(slot, index)
                schema = c.load(schema_path)
                task_ids = [task["task_id"] for task in chunk]
                self.assertEqual(schema["properties"]["items"]["required"], task_ids)
                self.assertEqual(set(schema["properties"]["items"]["properties"]), set(task_ids))
                self.assertFalse(schema["properties"]["items"]["additionalProperties"])
                good = {
                    "slot": slot,
                    "items": {task_id: {"supported": True, "reason": "合成理由"} for task_id in task_ids},
                }
                jsonschema.validate(good, schema)
                normalized = a.normalize_keyed_review(good, chunk)
                self.assertEqual([item["task_id"] for item in normalized["items"]], task_ids)
                if task_ids:
                    missing = {"slot": slot, "items": dict(good["items"])}
                    del missing["items"][task_ids[0]]
                    with self.assertRaises(jsonschema.ValidationError):
                        jsonschema.validate(missing, schema)
                total += 1
        self.assertEqual(total, c.CONFIG["analysis_v3_4"]["review_calls"])

    def test_v35_quota_resume_plan_is_exactly_fifteen_calls(self):
        codings = a.load_v32_codings()
        blinded = c.load(a.V32_RUN / "answers_blinded.json")
        counts = {}
        for slot in c.CONFIG["analysis_v3_5"]["new_review_slots"]:
            chunks = a.review_chunks(p.review_tasks_for(slot, codings, blinded))
            counts[slot] = len(chunks)
            self.assertEqual(len(chunks), 5)
        self.assertEqual(counts, {"O1": 5, "O2": 5, "O3": 5})
        self.assertEqual(sum(counts.values()), c.CONFIG["analysis_v3_5"]["review_calls"])
        # 先前实际请求：v3.2=36、v3.3=7、v3.4=12；v3.5 最多再开 23 次。
        self.assertEqual(36 + 7 + 12 + 23, 78)

    def test_legacy_cli_cannot_bypass_calibration(self):
        with self.assertRaisesRegex(SystemExit, "禁止直接执行 legacy pipeline"):
            p.main()

    def test_analysis_source_hashes_are_frozen(self):
        cfg = c.CONFIG["analysis_v2"]
        self.assertEqual(
            cfg["source_generation_manifest_sha256"],
            "5b9614f82d0f2d953223902a6496d692b08894dc78ea07c4f6c9378f0e3653aa",
        )
        self.assertEqual(cfg["source_answers_blinded_sha256"], c.sha256(c.SOURCE_RUN_DIR / "answers_blinded.json"))
        self.assertEqual(cfg["source_answers_unblinded_sha256"], c.sha256(c.SOURCE_RUN_DIR / "answers_unblinded.json"))

    def test_menu_definitions(self):
        defs = c.menu_definitions()
        self.assertEqual(sum(key.startswith("S2-") for key in defs), 6)
        self.assertEqual(sum(key.startswith("S8-") for key in defs), 8)
        self.assertEqual(sum(key.startswith("S10-") for key in defs), 8)

    def test_question_menu_is_isolated(self):
        self.assertIn("S2-D1", p.question_menu("S2"))
        self.assertNotIn("S8-D1", p.question_menu("S2"))
        self.assertIn("S10-D8", p.question_menu("S10"))


def synthetic_transport_doc(method: str = "menu") -> dict:
    synthetic = c.load(HERE / "16_synthetic_calibration.json")
    synthetic_answers = a.calibration_answers(synthetic)

    def span_id(block_id: str, label: str, evidence: str) -> str:
        spans = a.evidence_spans(synthetic_answers[block_id][label], label)
        matches = [key for key, value in spans.items() if evidence in value["text"]]
        if len(matches) != 1:
            raise AssertionError(
                f"合成材料证据应唯一命中一个片段：{block_id}/{label}/{evidence} -> {matches}"
            )
        return matches[0]

    def direction(
        block_id: str,
        label: str,
        local_id: str,
        menu_id: str,
        evidence: str,
        tag: str,
    ) -> dict:
        return {
            "definition": None if method == "menu" else f"{evidence}所代表的独立方向",
            "evidence_span_id": span_id(block_id, label, evidence),
            "local_id": local_id,
            "menu_id": menu_id if method == "menu" else None,
            "name": None if method == "menu" else f"方向{local_id}",
            "tag": tag,
        }

    specs = {
        "S2-B17": {
            "A": [("S2-D2", "修理成本", "数学")],
            "B": [
                ("S2-D6", "家人的回忆", "非数学"),
                ("S2-D4", "减少浪费", "非数学"),
                ("S2-D1", "继续使用", "非数学"),
            ],
            "C": [("S2-D2", "修理成本", "数学")],
        },
        "S2-B18": {
            "A": [
                ("S2-D1", "继续使用", "非数学"),
                ("S2-D3", "个人回忆", "非数学"),
            ],
            "B": [
                ("S2-D1", "继续使用", "非数学"),
                ("S2-D3", "个人回忆", "非数学"),
            ],
            "C": [("S2-D2", "修理成本", "数学")],
        },
    }
    choices = synthetic["expected_choices"]
    blocks = []
    for block_id, labels in specs.items():
        answers = {}
        for label, rows in labels.items():
            answers[label] = {
                "directions": [
                    direction(block_id, label, f"d{index}", menu_id, evidence, tag)
                    for index, (menu_id, evidence, tag) in enumerate(rows, 1)
                ],
                "identity_evidence_span_id": (
                    span_id(block_id, label, "数学系学生")
                    if block_id == "S2-B17" and label == "C"
                    else None
                ),
                "identity_explicit": block_id == "S2-B17" and label == "C",
            }
        comparisons = {}
        for pair, accounts in choices[block_id].items():
            comparisons[pair] = {}
            for account, choice in accounts.items():
                decisive = None
                if choice in c.LABELS:
                    needed = "数学" if account == "math_focus" else "非数学"
                    chosen = next(row for row in answers[choice]["directions"] if row["tag"] == needed)
                    decisive = {"answer": choice, "local_id": chosen["local_id"]}
                comparisons[pair][account] = {
                    "choice": choice,
                    "decisive": decisive,
                    "reason": "合成金标准",
                }
        blocks.append({"answers": answers, "block_id": block_id, "comparisons": comparisons})
    return {"blocks": blocks, "method": method, "question": "S2", "slot": "M1" if method == "menu" else "O1"}


class TestAnalysisV2Transport(unittest.TestCase):
    def test_nullable_decisive_schema_is_equivalent_without_oneof(self):
        schema = c.load(HERE / "15_schema_transport.json")
        self.assertNotIn('"oneOf"', json.dumps(schema, ensure_ascii=False))
        doc = synthetic_transport_doc("menu")
        jsonschema.validate(doc, schema)
        doc["blocks"][0]["comparisons"]["A_vs_B"]["math_focus"]["decisive"] = None
        jsonschema.validate(doc, schema)
        doc["blocks"][0]["comparisons"]["A_vs_B"]["math_focus"]["decisive"] = {"answer": "A"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_synthetic_menu_transport_expands_to_canonical(self):
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        answers = a.calibration_answers(synthetic)
        doc = synthetic_transport_doc("menu")
        jsonschema.validate(doc, c.load(HERE / "15_schema_transport.json"))
        self.assertEqual(a.validate_transport(doc, "M1", "S2", answers), [])
        self.assertEqual(a.validate_calibration_gold(doc, synthetic), [])
        expanded = a.expand_transport(doc, answers)
        self.assertEqual(a.validate_expanded(expanded, answers), [])
        direction = expanded["blocks"][0]["answers"]["B"]["directions"][0]
        self.assertEqual(direction["name"], "共同意义")
        self.assertEqual(direction["menu_id"], "S2-D6")
        self.assertIn(direction["evidence"], answers["S2-B17"]["B"])

    def test_synthetic_open_transport_passes_gold(self):
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        answers = a.calibration_answers(synthetic)
        doc = synthetic_transport_doc("open")
        self.assertEqual(a.validate_transport(doc, "O1", "S2", answers), [])
        self.assertEqual(a.validate_calibration_gold(doc, synthetic), [])
        self.assertEqual(
            a.validate_expanded(a.expand_transport(doc, answers), answers),
            [],
        )

    def test_transport_rejects_unknown_evidence_span_id(self):
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        answers = a.calibration_answers(synthetic)
        doc = synthetic_transport_doc("menu")
        doc["blocks"][0]["answers"]["A"]["directions"][0]["evidence_span_id"] = "A-E999"
        errors = a.validate_transport(doc, "M1", "S2", answers)
        self.assertTrue(any("证据片段编号无效" in error for error in errors))

    def test_evidence_spans_are_exact_and_label_scoped(self):
        text = "第一句，同一片段。第二句：还有一层；最后。"
        spans = a.evidence_spans(text, "B")
        self.assertTrue(spans)
        self.assertTrue(all(key.startswith("B-E") for key in spans))
        self.assertTrue(all(value["text"] in text for value in spans.values()))
        self.assertEqual([value["text"] for value in spans.values()][0], "第一句，")

    def test_render_blocks_exposes_span_ids_not_copy_task(self):
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        answers = a.calibration_answers(synthetic)
        rendered = a.render_blocks("S2", synthetic["question_text"], answers)
        self.assertIn("[A-E001]", rendered)
        self.assertIn("[B-E001]", rendered)
        self.assertIn("[C-E001]", rendered)

    def test_calibration_length_matches_formal_answer_scale(self):
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        answers = a.calibration_answers(synthetic)
        lengths = [len(text) for block in answers.values() for text in block.values()]
        self.assertGreaterEqual(min(lengths), 1600)
        self.assertLessEqual(max(lengths), 2000)

    def test_chunk_plan_is_32_new_calls_plus_16_reused_calls(self):
        blinded = c.load(c.SOURCE_RUN_DIR / "answers_blinded.json")
        per_slot = sum(len(a.chunks_for_question(blinded, question)) for question in c.CONFIG["questions"])
        self.assertEqual(per_slot, 8)
        self.assertEqual(per_slot * len(c.CONFIG["analysis_v2"]["encoding_slots"]), 32)
        self.assertEqual(per_slot * len(c.CONFIG["analysis_v2"]["reused_slots"]), 16)
        self.assertTrue(all(
            len(chunk) <= 2
            for question in c.CONFIG["questions"]
            for chunk in a.chunks_for_question(blinded, question)
        ))

    def test_codex_menu_split_schema_structurally_forbids_name_on_menu_direction(self):
        schema = c.load(HERE / "15_schema_transport_codex_menu.json")
        base = synthetic_transport_doc("menu")
        base["slot"] = "M3"
        blocks = []
        for block in base["blocks"]:
            answers = {}
            for label in c.LABELS:
                coded = block["answers"][label]
                menu_directions = []
                extra_directions = []
                for direction in coded["directions"]:
                    if direction["menu_id"] is not None:
                        menu_directions.append({
                            "evidence_span_id": direction["evidence_span_id"],
                            "local_id": direction["local_id"],
                            "menu_id": direction["menu_id"],
                            "tag": direction["tag"],
                        })
                    else:
                        extra_directions.append({
                            "definition": direction["definition"],
                            "evidence_span_id": direction["evidence_span_id"],
                            "local_id": direction["local_id"],
                            "name": direction["name"],
                            "tag": direction["tag"],
                        })
                answers[label] = {
                    "extra_directions": extra_directions,
                    "identity_evidence_span_id": coded["identity_evidence_span_id"],
                    "identity_explicit": coded["identity_explicit"],
                    "menu_directions": menu_directions,
                }
            blocks.append({
                "answers": answers,
                "block_id": block["block_id"],
                "comparisons": block["comparisons"],
            })
        split_doc = {"blocks": blocks, "method": "menu", "question": "S2", "slot": "M3"}
        jsonschema.validate(split_doc, schema)
        normalized = a.normalize_transport(split_doc, "M3")
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        answers = a.calibration_answers(synthetic)
        self.assertEqual(a.validate_transport(normalized, "M3", "S2", answers), [])
        split_doc["blocks"][0]["answers"]["A"]["menu_directions"][0]["name"] = "禁止字段"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(split_doc, schema)

    def test_codex_strict_schema_types_every_enum_and_const(self):
        missing = []

        def visit(value, path=()):
            if isinstance(value, dict):
                if ("enum" in value or "const" in value) and "type" not in value:
                    missing.append("/".join(map(str, path)))
                for key, child in value.items():
                    visit(child, path + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, path + (index,))

        for slot in ("M3", "O3"):
            visit(c.load(a.transport_schema(slot)), (slot,))
        self.assertEqual(missing, [])

    def test_codex_open_schema_diff_is_only_explicit_enum_types(self):
        generic = c.load(HERE / "15_schema_transport.json")
        strict = c.load(HERE / "17_schema_transport_codex_open.json")

        def strip_redundant_types(value):
            if isinstance(value, dict):
                return {
                    key: strip_redundant_types(child)
                    for key, child in value.items()
                    if not (key == "type" and ("enum" in value or "const" in value))
                }
            if isinstance(value, list):
                return [strip_redundant_types(child) for child in value]
            return value

        self.assertEqual(strip_redundant_types(strict), generic)

    def test_m3_uses_split_prompt_and_schema(self):
        synthetic = c.load(HERE / "16_synthetic_calibration.json")
        prompt = a.render_transport_prompt(
            "M3", synthetic["question"], synthetic["question_text"], a.calibration_answers(synthetic)
        )
        self.assertIn("`menu_directions`", prompt)
        self.assertIn("`extra_directions`", prompt)
        self.assertEqual(a.transport_schema("M3").name, "15_schema_transport_codex_menu.json")
        self.assertEqual(a.transport_schema("O3").name, "17_schema_transport_codex_open.json")
        self.assertEqual(a.transport_schema("M1").name, "15_schema_transport.json")


class TestStageIntegrity(unittest.TestCase):
    def test_stage_manifest_detects_modified_output(self):
        original = c.RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                c.RUN_DIR = Path(directory)
                target = c.RUN_DIR / "effective" / "x.txt"
                target.parent.mkdir(parents=True)
                target.write_text("原始", encoding="utf-8")
                c.write_stage_manifest("synthetic", [target])
                c.verify_stage_manifest("synthetic")
                target.write_text("被改", encoding="utf-8")
                with self.assertRaises(SystemExit):
                    c.verify_stage_manifest("synthetic")
        finally:
            c.RUN_DIR = original

    def test_valid_raw_must_match_prompt_and_effective_output(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            c.dump({
                "effective_sha256": c.sha256_text("回答"),
                "model": "test-model",
                "prompt_sha256": c.sha256_text("提示"),
                "provider": "claude",
                "raw": {"command_shape": {
                    "effort": "low", "model": "test-model", "provider": "claude",
                    "system_prompt_sha256": c.sha256_text(""),
                }, "parsed": {"result": "回答"}},
                "valid": True,
            }, raw / "attempt1.json")
            self.assertTrue(c.has_valid_raw(
                raw, c.sha256_text("提示"), c.sha256_text("回答"),
                "claude", "test-model", "low", c.sha256_text(""), json_mode=False
            ))
            self.assertFalse(c.has_valid_raw(
                raw, c.sha256_text("提示"), c.sha256_text("篡改"),
                "claude", "test-model", "low", c.sha256_text(""), json_mode=False
            ))

    def test_valid_raw_recovers_missing_effective_without_new_call(self):
        original = c.RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                c.RUN_DIR = Path(directory) / "run"
                schema_path = Path(directory) / "schema.json"
                c.dump({
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "additionalProperties": False,
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                    "type": "object",
                }, schema_path)
                prompt = "合成提示"
                actual_prompt = c.prompt_with_json_schema(prompt, schema_path)
                doc = {"value": 7}
                unit_id = "RECOVER_TEST"
                raw_dir = c.RUN_DIR / "raw" / unit_id
                c.dump({
                    "attempt": 1,
                    "effective_sha256": c.sha256_text(c.canonical_json(doc)),
                    "errors": [],
                    "model": "test-model",
                    "prompt_sha256": c.sha256_text(actual_prompt),
                    "provider": "claude",
                    "raw": {
                        "command_shape": {
                            "effort": "low", "model": "test-model", "provider": "claude",
                            "system_prompt_sha256": c.sha256_text(""),
                            "output_schema_sha256": c.native_output_schema_sha(
                                "claude", schema_path
                            ),
                        },
                        "parsed": {
                            "result": json.dumps(doc),
                            "structured_output": doc,
                        },
                    },
                    "unit_id": unit_id,
                    "valid": True,
                }, raw_dir / "attempt1.json")
                output = c.RUN_DIR / "effective" / "recovered.json"
                with (
                    mock.patch.object(c, "verify_run_authorization"),
                    mock.patch.object(c, "provider_call", side_effect=AssertionError("must not call")),
                ):
                    got = c.run_json_unit(
                        unit_id, "claude", "test-model", "low", prompt,
                        schema_path, lambda value: [], output,
                    )
                self.assertEqual(got, doc)
                self.assertEqual(c.load(output), doc)
        finally:
            c.RUN_DIR = original

    def test_json_schema_is_in_actual_prompt_before_provider_call(self):
        original = c.RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                c.RUN_DIR = Path(directory) / "run"
                schema_path = Path(directory) / "schema.json"
                schema = {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "additionalProperties": False,
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                    "type": "object",
                }
                c.dump(schema, schema_path)
                expected_prompt = c.prompt_with_json_schema("合成提示", schema_path)
                response = {
                    "ok": True,
                    "text": '{"value": 7}',
                    "raw": {"command_shape": {
                        "effort": "low", "model": "test-model", "provider": "claude",
                        "system_prompt_sha256": c.sha256_text(""),
                        "output_schema_sha256": c.native_output_schema_sha(
                            "claude", schema_path
                        ),
                    }, "parsed": {
                        "result": '{"value": 7}',
                        "structured_output": {"value": 7},
                    }},
                }
                output = c.RUN_DIR / "effective" / "result.json"
                with (
                    mock.patch.object(c, "verify_run_authorization"),
                    mock.patch.object(c, "provider_call", return_value=response) as provider,
                ):
                    got = c.run_json_unit(
                        "SCHEMA_PROMPT_TEST", "claude", "test-model", "low", "合成提示",
                        schema_path, lambda value: [], output,
                    )
                self.assertEqual(got, {"value": 7})
                self.assertEqual(
                    (c.RUN_DIR / "prompts" / "SCHEMA_PROMPT_TEST.txt").read_text(encoding="utf-8"),
                    expected_prompt,
                )
                self.assertEqual(provider.call_args.args[1], expected_prompt)
                self.assertEqual(provider.call_args.args[5], schema_path)
                self.assertIn('"required": [', expected_prompt)
                self.assertIn('"value"', expected_prompt)
        finally:
            c.RUN_DIR = original


class TestTransportFailures(unittest.TestCase):
    def test_claude_timeout_is_returned_as_recordable_failure(self):
        with mock.patch.object(
            c.subprocess, "run", side_effect=c.subprocess.TimeoutExpired("claude", 900)
        ):
            got = c.call_claude("提示", "claude-opus-4-6", None, "背景")
        self.assertFalse(got["ok"])
        self.assertTrue(got["raw"]["timed_out"])
        self.assertEqual(got["raw"]["command_shape"]["effort"], "default_unset")

    def test_codex_timeout_is_returned_as_recordable_failure(self):
        with mock.patch.object(
            c.subprocess, "run", side_effect=c.subprocess.TimeoutExpired("codex", 900)
        ):
            got = c.call_codex("提示", "gpt-5.4", "low")
        self.assertFalse(got["ok"])
        self.assertTrue(got["raw"]["timed_out"])

    def test_codex_native_output_schema_is_passed_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            c.dump({
                "additionalProperties": False,
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "type": "object",
            }, schema_path)
            seen = {}

            def fake_run(cmd, **kwargs):
                seen["cmd"] = cmd
                stdout = json.dumps({
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "{\"value\":7}"},
                }) + "\n"
                return c.subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

            with mock.patch.object(c.subprocess, "run", side_effect=fake_run):
                got = c.call_codex("提示", "gpt-5.4", "low", schema_path)
            self.assertTrue(got["ok"])
            self.assertIn("--output-schema", seen["cmd"])
            index = seen["cmd"].index("--output-schema")
            self.assertEqual(seen["cmd"][index + 1], str(schema_path.resolve()))
            self.assertEqual(
                got["raw"]["command_shape"]["output_schema_sha256"],
                c.sha256(schema_path),
            )

    def test_claude_native_output_schema_is_passed_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            schema = {
                "additionalProperties": False,
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "type": "object",
            }
            c.dump(schema, schema_path)
            seen = {}

            def fake_run(cmd, **kwargs):
                seen["cmd"] = cmd
                stdout = json.dumps({
                    "is_error": False,
                    "modelUsage": {"claude-opus-4-6": {"inputTokens": 1}},
                    "num_turns": 2,
                    "permission_denials": [],
                    "result": "{\"value\":7}",
                    "structured_output": {"value": 7},
                })
                return c.subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

            with mock.patch.object(c.subprocess, "run", side_effect=fake_run):
                got = c.call_claude(
                    "提示", "claude-opus-4-6", "low", "", schema_path
                )
            self.assertTrue(got["ok"])
            self.assertEqual(c.parse_exact_json(got["text"]), {"value": 7})
            self.assertIn("--json-schema", seen["cmd"])
            index = seen["cmd"].index("--json-schema")
            self.assertEqual(
                json.loads(seen["cmd"][index + 1]),
                schema,
            )
            self.assertEqual(
                got["raw"]["command_shape"]["output_schema_sha256"],
                c.native_output_schema_sha("claude", schema_path),
            )

    def test_claude_native_schema_strips_only_root_draft_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": {"value": {"type": "integer"}},
                "properties": {"value": {"$ref": "#/$defs/value"}},
                "required": ["value"],
                "type": "object",
            }
            c.dump(schema, schema_path)
            native = c.native_output_schema("claude", schema_path)
            self.assertNotIn("$schema", native)
            self.assertEqual(native["$defs"], schema["$defs"])
            self.assertEqual(
                c.native_output_schema("codex", schema_path),
                schema,
            )

    def test_claude_native_output_schema_rejects_mismatched_result(self):
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            c.dump({
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "type": "object",
            }, schema_path)
            stdout = json.dumps({
                "is_error": False,
                "modelUsage": {"claude-opus-4-6": {"inputTokens": 1}},
                "num_turns": 2,
                "permission_denials": [],
                "result": "{\"value\":8}",
                "structured_output": {"value": 7},
            })
            completed = c.subprocess.CompletedProcess(
                ["claude"], 0, stdout=stdout, stderr=""
            )
            with mock.patch.object(c.subprocess, "run", return_value=completed):
                got = c.call_claude(
                    "提示", "claude-opus-4-6", "low", "", schema_path
                )
            self.assertFalse(got["ok"])
            self.assertIn("不一致", got["error"])

    def test_ninth_first_failure_is_reconstructed_from_raw(self):
        original = c.RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                c.RUN_DIR = Path(directory)
                for index in range(1, 10):
                    c.dump({
                        "attempt": 1, "unit_id": f"U{index}", "valid": False,
                    }, c.RUN_DIR / "raw" / f"U{index}" / "attempt1.json")
                with self.assertRaises(SystemExit):
                    c.enforce_request_limits(before_new_request=True)
        finally:
            c.RUN_DIR = original

    def test_calibration_mode_never_retries(self):
        original = c.RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                c.RUN_DIR = Path(directory) / "run"
                schema_path = Path(directory) / "schema.json"
                c.dump({
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                    "type": "object",
                }, schema_path)
                with (
                    mock.patch.object(c, "verify_run_authorization"),
                    mock.patch.object(c, "provider_call", return_value={
                        "ok": False,
                        "error": "合成失败",
                        "raw": {"command_shape": {
                            "effort": "low", "model": "test-model", "provider": "claude",
                            "system_prompt_sha256": c.sha256_text(""),
                        }},
                    }) as provider,
                    self.assertRaises(SystemExit),
                ):
                    c.run_json_unit(
                        "CAL_NO_RETRY", "claude", "test-model", "low", "提示",
                        schema_path, lambda value: [],
                        c.RUN_DIR / "effective" / "result.json", max_attempts=1,
                    )
                self.assertEqual(provider.call_count, 1)
                self.assertTrue((c.RUN_DIR / "raw" / "CAL_NO_RETRY" / "attempt1.json").exists())
                self.assertFalse((c.RUN_DIR / "raw" / "CAL_NO_RETRY" / "attempt2.json").exists())
        finally:
            c.RUN_DIR = original

    def test_in_flight_record_exists_before_provider_exception(self):
        original = c.RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                c.RUN_DIR = Path(directory) / "run"
                schema_path = Path(directory) / "schema.json"
                c.dump({
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"], "type": "object",
                }, schema_path)
                with (
                    mock.patch.object(c, "verify_run_authorization"),
                    mock.patch.object(c, "provider_call", side_effect=RuntimeError("crash")),
                    self.assertRaises(RuntimeError),
                ):
                    c.run_json_unit(
                        "CRASH_TEST", "claude", "test-model", "low", "提示",
                        schema_path, lambda value: [],
                        c.RUN_DIR / "effective" / "result.json",
                    )
                pending = c.load(c.RUN_DIR / "raw" / "CRASH_TEST" / "attempt1.json")
                self.assertFalse(pending["valid"])
                self.assertTrue(pending["raw"]["in_flight"])
                self.assertIsNotNone(pending["request_registered_at_utc"])
                self.assertIsNone(pending["response_recorded_at_utc"])
                self.assertEqual(c.state()["request_attempts"], 1)
        finally:
            c.RUN_DIR = original


def synthetic_comparison(score: int) -> dict:
    focal, reference = "B", "C"
    if score == 1:
        math_result, nonmath_result = focal, reference
    elif score == -1:
        math_result, nonmath_result = reference, focal
    else:
        math_result = nonmath_result = "相当"
    methods = {}
    for method in ("menu", "open"):
        methods[method] = {
            "accounts": {
                "math_focus": {"result": math_result, "status": "direction" if score else "equal"},
                "nonmath_breadth": {"result": nonmath_result, "status": "direction" if score else "equal"},
            },
            "score": score,
        }
    return {
        "consensus": score, "focal_label": focal, "reference_label": reference,
        "methods": methods,
    }


class TestRegisteredReporting(unittest.TestCase):
    def test_cross_question_repetition_requires_both_questions(self):
        comparisons, blocks = {}, {}
        for question, scores in {"S2": [1, 1, 1, 0, 0, 0], "S10": [1, 1, 0, 0, 0, 0]}.items():
            for index, score in enumerate(scores, 1):
                block_id = f"{question}-B{index:02d}"
                comparisons[block_id] = synthetic_comparison(score)
                blocks[block_id] = {"question": question}
        got = p.cross_question_summary(comparisons, {"blocks": blocks}, True)
        self.assertTrue(got["per_question"]["S2"]["repetition_threshold_met"])
        self.assertFalse(got["per_question"]["S10"]["repetition_threshold_met"])
        self.assertFalse(got["repeated_across_both_questions"])

    def test_separate_accounts_do_not_replace_joint_score(self):
        got = p.primary_account_summary([synthetic_comparison(1)])
        self.assertEqual(got["methods"]["menu"]["math_focus"]["M_more"], 1)
        self.assertEqual(got["methods"]["menu"]["nonmath_breadth"]["N_more"], 1)
        self.assertIn("不得替代", got["warning"])

    def test_aggregate_smoke_writes_all_registered_sections(self):
        equal = {"choice": "相当", "decisive": None, "reason": "合成相当"}
        codings = {slot: {} for slot in c.CONFIG["coding_slots"]}
        unblinded = {"blocks": {}}
        blinded = {"blocks": {}}
        by_question = {question: [] for question in c.CONFIG["questions"]}
        for block_id, mapping in c.RANDOM_TABLE["blind_mapping"].items():
            question = block_id.split("-B", 1)[0]
            by_question[question].append(block_id)
            unblinded["blocks"][block_id] = {
                "question": question, "blind_mapping": mapping,
                "char_lengths": {arm: 100 for arm in ("N", "G", "M")},
            }
            blinded["blocks"][block_id] = {
                "question": question,
                "answers": {label: f"{block_id}-{label}" for label in c.LABELS},
            }
        for slot, spec in c.CONFIG["coding_slots"].items():
            for question, block_ids in by_question.items():
                blocks = []
                for block_id in block_ids:
                    blocks.append({
                        "block_id": block_id,
                        "answers": {
                            label: {"directions": [], "identity_explicit": False, "identity_evidence": None}
                            for label in c.LABELS
                        },
                        "comparisons": {
                            pair: {
                                account: copy.deepcopy(equal) for account in c.ACCOUNTS
                            } for pair in c.PAIRS
                        },
                    })
                codings[slot][question] = {
                    "blocks": blocks, "method": spec["method"],
                    "question": question, "slot": slot,
                }
        original_run = p.RUN
        try:
            with tempfile.TemporaryDirectory() as directory:
                p.RUN = Path(directory)
                c.dump(unblinded, p.RUN / "answers_unblinded.json")
                c.dump(blinded, p.RUN / "answers_blinded.json")
                with (
                    mock.patch.object(c, "verify_run_authorization"),
                    mock.patch.object(c, "verify_stage_manifest"),
                    mock.patch.object(c, "write_stage_manifest"),
                    mock.patch.object(c, "enforce_request_limits"),
                    mock.patch.object(p, "load_codings", return_value=codings),
                    mock.patch.object(p, "review_index", return_value={}),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    p.run_aggregate()
                summary = c.load(p.RUN / "summary.json")
                audit = c.load(p.RUN / "audit.json")
                self.assertIn("cross_question_repetition", summary)
                self.assertIn("primary_separate_accounts", summary)
                self.assertIn("descriptive_G_vs_N", summary)
                self.assertFalse(summary["primary_M_vs_N"]["pass"])
                self.assertIsNone(summary["secondary_M_vs_G"]["pass"])
                self.assertFalse(summary["secondary_M_vs_G"]["inferentially_tested"])
                self.assertIn("decisive_evidence_locations", audit)
        finally:
            p.RUN = original_run


if __name__ == "__main__":
    unittest.main(verbosity=2)
