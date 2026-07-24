#!/usr/bin/env python3
"""正式实验分阶段执行入口。未存在开跑登记时，所有模型调用都会 fail-closed。"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import jsonschema

import core as c


HERE = c.HERE
RUN = c.RUN_DIR
EFFECTIVE = RUN / "effective"


def request_artifacts(unit_ids: list[str]) -> list[Path]:
    paths = []
    for unit_id in unit_ids:
        prompt = RUN / "prompts" / f"{unit_id}.txt"
        attempts = sorted((RUN / "raw" / unit_id).glob("attempt*.json"))
        if not prompt.is_file() or not attempts:
            raise SystemExit(f"调用单元证据链不完整：{unit_id}")
        paths.append(prompt)
        paths.extend(attempts)
    return paths


def require_sentinel_pass() -> None:
    path = RUN / "02_sentinel_report.json"
    if not path.exists() or c.load(path).get("status") != "PASS":
        raise SystemExit("哨兵门未通过，拒绝进入研究回答阶段")


def render_sentinel_prompt(slot: str) -> str:
    template = (HERE / "11_prompt_sentinel.md").read_text(encoding="utf-8")
    tasks = {task["task_id"]: task for task in c.load(HERE / "05_sentinel_tasks.json")["tasks"]}
    order = c.RANDOM_TABLE["sentinel_task_order"][slot]
    rows = []
    for task_id in order:
        task = tasks[task_id]
        rows.append(
            f"【{task_id}】\n问题：{task['question']}\nA：{task['A']}\nB：{task['B']}"
        )
    return template.replace("{{SLOT}}", slot).replace("{{TASKS}}", "\n\n".join(rows))


def validate_sentinel(doc: dict, slot: str) -> list[str]:
    errors = []
    if doc.get("slot") != slot:
        errors.append("slot 不符")
    ids = [item.get("task_id") for item in doc.get("items", [])]
    expected = {f"T{i}" for i in range(1, 7)}
    if set(ids) != expected or len(ids) != len(set(ids)):
        errors.append(f"任务集合不符：{ids}")
    return errors


def sentinel_report(docs: dict[str, dict]) -> dict:
    tasks = {task["task_id"]: task for task in c.load(HERE / "05_sentinel_tasks.json")["tasks"]}
    by_slot = {
        slot: {item["task_id"]: item for item in doc["items"]}
        for slot, doc in docs.items()
    }
    groups = {"menu": ("M1", "M2", "M3"), "open": ("O1", "O2", "O3")}
    checks = []
    for method, slots in groups.items():
        for task_id, task in sorted(tasks.items()):
            for account in ("math_focus", "nonmath_breadth"):
                votes = {slot: by_slot[slot][task_id][account] for slot in slots}
                result = c.group_vote(votes)
                expected = task["expected"][account]
                mapping = {"equal": "相当", "cannot": "无法判断", "A": "A", "B": "B"}
                ok = result["result"] == mapping[expected]
                checks.append({
                    "account": account, "expected": mapping[expected], "method": method,
                    "ok": ok, "result": result, "task_id": task_id,
                })
    per_slot_cannot = {
        slot: any(
            item[account] == "无法判断"
            for item in doc["items"] for account in ("math_focus", "nonmath_breadth")
        )
        for slot, doc in docs.items()
    }
    status = "PASS" if all(row["ok"] for row in checks) and all(per_slot_cannot.values()) else "FAIL"
    return {"checks": checks, "per_slot_used_cannot": per_slot_cannot, "status": status}


def run_sentinel() -> None:
    c.verify_run_authorization()
    docs = {}
    for slot, spec in sorted(c.CONFIG["coding_slots"].items()):
        prompt = render_sentinel_prompt(slot)
        docs[slot] = c.run_json_unit(
            unit_id=f"SENTINEL_{slot}", provider=spec["provider"], model=spec["model"],
            effort=spec["effort"], prompt=prompt, schema_path=HERE / "10_schema_sentinel.json",
            semantic_validate=lambda doc, slot=slot: validate_sentinel(doc, slot),
            output_path=EFFECTIVE / "sentinel" / f"{slot}.json",
        )
    report = sentinel_report(docs)
    c.dump(report, RUN / "02_sentinel_report.json")
    if report["status"] != "PASS":
        raise SystemExit("哨兵测量失败；不得生成研究回答")
    c.write_stage_manifest(
        "sentinel",
        [EFFECTIVE / "sentinel" / f"{slot}.json" for slot in c.CONFIG["coding_slots"]]
        + [RUN / "00_open_run.json", RUN / "02_sentinel_report.json"]
        + request_artifacts([f"SENTINEL_{slot}" for slot in c.CONFIG["coding_slots"]]),
    )
    print("[PASS] 六槽位哨兵门")


def build_answer_files() -> tuple[dict, dict]:
    unblinded = {"blocks": {}, "model": c.CONFIG["generation"]["model"]}
    blinded = {"blocks": {}}
    for block_id, mapping in sorted(c.RANDOM_TABLE["blind_mapping"].items()):
        question = block_id.split("-B", 1)[0]
        arm_text = {}
        for arm in ("N", "G", "M"):
            path = EFFECTIVE / "generation" / f"{block_id}_{arm}.txt"
            if not path.exists():
                raise SystemExit(f"缺生成回答：{path.name}")
            arm_text[arm] = path.read_text(encoding="utf-8")
        unblinded["blocks"][block_id] = {
            "question": question,
            "arms": arm_text,
            "char_lengths": {arm: len(text.strip()) for arm, text in arm_text.items()},
            "blind_mapping": mapping,
        }
        blinded["blocks"][block_id] = {
            "question": question,
            "answers": {label: arm_text[arm] for label, arm in mapping.items()},
        }
    c.dump(unblinded, RUN / "answers_unblinded.json")
    c.dump(blinded, RUN / "answers_blinded.json")
    return unblinded, blinded


def run_generate() -> None:
    c.verify_run_authorization()
    c.verify_stage_manifest("sentinel")
    require_sentinel_pass()
    spec = c.CONFIG["generation"]
    for row in c.RANDOM_TABLE["generation_order"]:
        block_id, arm = row["block_id"], row["arm"]
        question = c.CONFIG["questions"][row["question"]]["text"]
        unit = f"GEN_{row['call_index']:02d}_{block_id}_{arm}"
        print(f"[{row['call_index']:02d}/48] {block_id}/{arm}", flush=True)
        c.run_text_unit(
            unit_id=unit, provider=spec["provider"], model=spec["model"], effort=None,
            prompt=question, system=c.CONFIG["arms"][arm],
            output_path=EFFECTIVE / "generation" / f"{block_id}_{arm}.txt",
        )
    build_answer_files()
    generation_units = [
        f"GEN_{row['call_index']:02d}_{row['block_id']}_{row['arm']}"
        for row in c.RANDOM_TABLE["generation_order"]
    ]
    c.write_stage_manifest(
        "generation",
        [
            EFFECTIVE / "generation" / f"{row['block_id']}_{row['arm']}.txt"
            for row in c.RANDOM_TABLE["generation_order"]
        ]
        + [
            RUN / "answers_blinded.json", RUN / "answers_unblinded.json",
            RUN / "manifest_sentinel.json",
        ]
        + request_artifacts(generation_units),
    )
    print("[PASS] 48 份研究回答生成完成")


def question_menu(question: str) -> str:
    text = (HERE / "03_menu_excerpt.md").read_text(encoding="utf-8")
    display = "S8'" if question == "S8" else ("S10'" if question == "S10" else question)
    start = text.index(f"### {display}〔")
    next_pos = text.find("\n### ", start + 4)
    return text[start:] if next_pos < 0 else text[start:next_pos]


def blocks_for_question(blinded: dict, question: str) -> dict[str, dict[str, str]]:
    return {
        block_id: value["answers"]
        for block_id, value in blinded["blocks"].items()
        if value["question"] == question
    }


def render_coding_prompt(slot: str, question: str, answers: dict) -> str:
    method = c.CONFIG["coding_slots"][slot]["method"]
    template_name = "20_prompt_coding_menu.md" if method == "menu" else "21_prompt_coding_open.md"
    template = (HERE / template_name).read_text(encoding="utf-8")
    rows = [f"题目：{c.CONFIG['questions'][question]['text']}"]
    for block_id, values in sorted(answers.items()):
        rows.append(
            f"【块 {block_id}】\n"
            f"A：{values['A']}\n\nB：{values['B']}\n\nC：{values['C']}"
        )
    prompt = template.replace("{{SLOT}}", slot).replace("{{BLOCKS}}", "\n\n".join(rows))
    if method == "menu":
        prompt = prompt.replace("{{MENU}}", question_menu(question))
    return prompt


def encode_unit_id(slot: str, question: str) -> str:
    return f"ENCODE_V12_{slot}_{question}"


def run_encode() -> None:
    c.verify_run_authorization()
    c.verify_stage_manifest("sentinel")
    c.verify_stage_manifest("generation")
    require_sentinel_pass()
    if not (RUN / "answers_blinded.json").exists():
        raise SystemExit("缺盲化回答，拒绝编码")
    blinded = c.load(RUN / "answers_blinded.json")
    for slot, spec in sorted(c.CONFIG["coding_slots"].items()):
        for question in c.RANDOM_TABLE["encoding_question_order"][slot]:
            answers = blocks_for_question(blinded, question)
            prompt = render_coding_prompt(slot, question, answers)
            schema = HERE / ("12_schema_coding_menu.json" if spec["method"] == "menu"
                             else "13_schema_coding_open.json")
            print(f"[ENCODE] {slot}/{question}", flush=True)
            c.run_json_unit(
                unit_id=encode_unit_id(slot, question), provider=spec["provider"],
                model=spec["model"], effort=spec["effort"], prompt=prompt,
                schema_path=schema,
                semantic_validate=lambda doc, slot=slot, question=question, answers=answers:
                    c.validate_coding(doc, slot, question, answers),
                output_path=EFFECTIVE / "coding" / f"{slot}_{question}.json",
            )
    c.write_stage_manifest(
        "coding",
        [
            EFFECTIVE / "coding" / f"{slot}_{question}.json"
            for slot in c.CONFIG["coding_slots"] for question in c.CONFIG["questions"]
        ] + [
            RUN / "manifest_generation.json",
            RUN / c.AUTH_FILENAME,
        ] + request_artifacts([
            encode_unit_id(slot, question)
            for slot in c.CONFIG["coding_slots"] for question in c.CONFIG["questions"]
        ]),
    )
    print("[PASS] 18 个主编码调用单元完成")


def load_codings() -> dict[str, dict[str, dict]]:
    blinded_path = RUN / "answers_blinded.json"
    if not blinded_path.exists():
        raise SystemExit("缺盲化回答，无法复验主编码")
    blinded = c.load(blinded_path)
    out = {}
    for slot, spec in c.CONFIG["coding_slots"].items():
        out[slot] = {}
        for question in c.CONFIG["questions"]:
            path = EFFECTIVE / "coding" / f"{slot}_{question}.json"
            if not path.exists():
                raise SystemExit(f"缺主编码：{path.name}")
            doc = c.load(path)
            schema_name = "12_schema_coding_menu.json" if spec["method"] == "menu" else "13_schema_coding_open.json"
            answers = blocks_for_question(blinded, question)
            errors = []
            try:
                jsonschema.validate(doc, c.load(HERE / schema_name))
                errors.extend(c.validate_coding(doc, slot, question, answers))
            except Exception as exc:
                errors.append(str(exc))
            if errors:
                raise SystemExit(f"主编码复验失败：{path.name}：{errors[:3]}")
            out[slot][question] = doc
    return out


def ticket_id(source: str, question: str, block_id: str, pair: str, account: str) -> str:
    return f"REV-{source}-{question}-{block_id}-{pair}-{account}"


def review_tasks_for(reviewer: str, codings: dict, blinded: dict) -> list[dict]:
    method = c.CONFIG["coding_slots"][reviewer]["method"]
    group = [slot for slot, spec in c.CONFIG["coding_slots"].items() if spec["method"] == method]
    tasks = []
    for source in group:
        if source == reviewer:
            continue
        for question, doc in codings[source].items():
            for block in doc["blocks"]:
                block_id = block["block_id"]
                for pair in c.PAIRS:
                    for account in c.ACCOUNTS:
                        verdict = block["comparisons"][pair][account]
                        if verdict["choice"] not in c.LABELS:
                            continue
                        decisive = verdict["decisive"]
                        answer = decisive["answer"]
                        answer_text = blinded["blocks"][block_id]["answers"][answer]
                        if c.locate_evidence(
                            answer_text, decisive["evidence"], decisive["occurrence"]
                        ) is None:
                            continue
                        tasks.append({
                            "account": account,
                            "answer": answer,
                            "answer_text": blinded["blocks"][block_id]["answers"][answer],
                            "block_id": block_id,
                            "definition": decisive["definition"],
                            "evidence": decisive["evidence"],
                            "name": decisive["name"],
                            "pair": pair,
                            "question": question,
                            "source_slot": source,
                            "task_id": ticket_id(source, question, block_id, pair, account),
                        })
    return sorted(tasks, key=lambda row: c.review_order_key(reviewer, row["task_id"]))


def render_review_prompt(slot: str, tasks: list[dict]) -> str:
    template = (HERE / "22_prompt_review.md").read_text(encoding="utf-8")
    rows = []
    for task in tasks:
        rows.append(
            f"【{task['task_id']}】\n完整回答：{task['answer_text']}\n"
            f"证据短语：{json.dumps(task['evidence'], ensure_ascii=False)}\n"
            f"方向名称：{task['name']}\n方向边界：{task['definition']}"
        )
    return template.replace("{{SLOT}}", slot).replace("{{TASKS}}", "\n\n".join(rows))


def validate_review(doc: dict, slot: str, tasks: list[dict]) -> list[str]:
    errors = []
    if doc.get("slot") != slot:
        errors.append("slot 不符")
    got = [item.get("task_id") for item in doc.get("items", [])]
    expected = {task["task_id"] for task in tasks}
    if set(got) != expected or len(got) != len(set(got)):
        errors.append(f"复核任务集不符：缺={sorted(expected-set(got))[:5]} 多={sorted(set(got)-expected)[:5]}")
    return errors


def run_review() -> None:
    c.verify_run_authorization()
    c.verify_stage_manifest("sentinel")
    c.verify_stage_manifest("generation")
    c.verify_stage_manifest("coding")
    require_sentinel_pass()
    blinded = c.load(RUN / "answers_blinded.json")
    codings = load_codings()
    called_units = []
    for slot, spec in sorted(c.CONFIG["coding_slots"].items()):
        tasks = review_tasks_for(slot, codings, blinded)
        if not tasks:
            c.dump({"slot": slot, "items": []}, EFFECTIVE / "review" / f"{slot}.json")
            no_calls = RUN / "no_call_units.json"
            rows = c.load(no_calls) if no_calls.exists() else []
            row = {"reason": "没有方向性决定证据需要复核", "unit_id": f"REVIEW_{slot}"}
            by_unit = {item["unit_id"]: item for item in rows}
            by_unit[row["unit_id"]] = row
            c.dump([by_unit[key] for key in sorted(by_unit)], no_calls)
            print(f"[REVIEW] {slot} tasks=0; no call", flush=True)
            continue
        prompt = render_review_prompt(slot, tasks)
        called_units.append(f"REVIEW_{slot}")
        print(f"[REVIEW] {slot} tasks={len(tasks)}", flush=True)
        c.run_json_unit(
            unit_id=f"REVIEW_{slot}", provider=spec["provider"], model=spec["model"],
            effort=spec["effort"], prompt=prompt, schema_path=HERE / "14_schema_review.json",
            semantic_validate=lambda doc, slot=slot, tasks=tasks: validate_review(doc, slot, tasks),
            output_path=EFFECTIVE / "review" / f"{slot}.json",
        )
    paths = [EFFECTIVE / "review" / f"{slot}.json" for slot in c.CONFIG["coding_slots"]]
    if (RUN / "no_call_units.json").exists():
        paths.append(RUN / "no_call_units.json")
    c.write_stage_manifest(
        "review",
        paths + [RUN / "manifest_coding.json"] + request_artifacts(called_units),
    )
    print("[PASS] 决定性证据复核阶段完成（空任务槽位不发请求）")


def review_index(codings: dict, blinded: dict) -> dict[tuple[str, str], bool]:
    index = {}
    for reviewer in c.CONFIG["coding_slots"]:
        path = EFFECTIVE / "review" / f"{reviewer}.json"
        if not path.exists():
            raise SystemExit(f"缺证据复核：{path.name}")
        doc = c.load(path)
        tasks = review_tasks_for(reviewer, codings, blinded)
        errors = []
        try:
            jsonschema.validate(doc, c.load(HERE / "14_schema_review.json"))
            errors.extend(validate_review(doc, reviewer, tasks))
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise SystemExit(f"证据复核文件复验失败：{path.name}：{errors[:3]}")
        for item in doc["items"]:
            index[(reviewer, item["task_id"])] = item["supported"]
    return index


def adjusted_choice(source: str, question: str, block: dict, pair: str,
                    account: str, reviews: dict,
                    answer_texts: dict[str, str]) -> tuple[str, dict]:
    verdict = block["comparisons"][pair][account]
    choice = verdict["choice"]
    if choice not in c.LABELS:
        return choice, {"review": "not_directional"}
    decisive = verdict["decisive"]
    answer = decisive["answer"]
    if c.locate_evidence(
        answer_texts[answer], decisive["evidence"], decisive["occurrence"]
    ) is None:
        return "无法判断", {
            "review": "evidence_location_failed",
            "reason": "精确匹配与仅移除 Markdown 强调标记后匹配均失败",
        }
    method = c.CONFIG["coding_slots"][source]["method"]
    group = [slot for slot, spec in c.CONFIG["coding_slots"].items() if spec["method"] == method]
    task = ticket_id(source, question, block["block_id"], pair, account)
    judgments = {reviewer: reviews[(reviewer, task)] for reviewer in group if reviewer != source}
    support = sum(judgments.values())
    if support == 0:
        return "无法判断", {"review": "downgraded", "judgments": judgments}
    if support == 1:
        return choice, {"review": "split", "judgments": judgments}
    return choice, {"review": "supported", "judgments": judgments}


def summarize_pair(codings: dict, reviews: dict, question: str, block_id: str,
                   mapping: dict, answer_texts: dict[str, str],
                   focal_arm: str, reference_arm: str) -> dict:
    pair, focal_label, reference_label = c.blind_pair(mapping, focal_arm, reference_arm)
    methods = {}
    for method, slots in {"menu": ("M1", "M2", "M3"), "open": ("O1", "O2", "O3")}.items():
        account_results = {}
        for account in c.ACCOUNTS:
            votes, review_meta = {}, {}
            for slot in slots:
                doc = codings[slot][question]
                block = next(row for row in doc["blocks"] if row["block_id"] == block_id)
                votes[slot], review_meta[slot] = adjusted_choice(
                    slot, question, block, pair, account, reviews, answer_texts
                )
            result = c.group_vote(votes)
            result["review_meta"] = review_meta
            account_results[account] = result
        score = c.method_score(
            account_results["math_focus"]["result"],
            account_results["nonmath_breadth"]["result"],
            focal_label, reference_label,
        )
        methods[method] = {"accounts": account_results, "score": score}
    consensus = methods["menu"]["score"] if methods["menu"]["score"] == methods["open"]["score"] else 0
    return {
        "blind_pair": pair, "focal_arm": focal_arm, "focal_label": focal_label,
        "reference_arm": reference_arm, "reference_label": reference_label,
        "methods": methods, "consensus": consensus,
    }


def sign_summary(rows: list[dict], min_positive: int) -> dict:
    scores = [row["consensus"] for row in rows]
    positive, negative = scores.count(1), scores.count(-1)
    n = positive + negative
    p = c.exact_sign_p(n, positive) if n else 1.0
    return {
        "blocks_total": len(rows), "consensus_positive": positive,
        "consensus_negative": negative, "consensus_zero": scores.count(0),
        "nonzero_n": n, "one_sided_exact_p": p,
        "pass": p <= c.CONFIG["thresholds"]["primary_alpha_one_sided"] and positive >= min_positive,
    }


def identity_summary(codings: dict, unblinded: dict) -> dict:
    out = {method: {arm: 0 for arm in ("N", "G", "M")} for method in ("menu", "open")}
    totals = {arm: 0 for arm in ("N", "G", "M")}
    for block_id, source in unblinded["blocks"].items():
        question = source["question"]
        inverse = {arm: label for label, arm in source["blind_mapping"].items()}
        for arm, label in inverse.items():
            totals[arm] += 1
            for method, slots in {"menu": ("M1", "M2", "M3"), "open": ("O1", "O2", "O3")}.items():
                votes = []
                for slot in slots:
                    doc = codings[slot][question]
                    block = next(row for row in doc["blocks"] if row["block_id"] == block_id)
                    votes.append(block["answers"][label]["identity_explicit"])
                if sum(votes) >= 2:
                    out[method][arm] += 1
    return {"counts": out, "denominators": totals}


def descriptive_score_summary(rows: list[dict]) -> dict:
    scores = [row["consensus"] for row in rows]
    return {
        "blocks_total": len(rows),
        "consensus_positive": scores.count(1),
        "consensus_negative": scores.count(-1),
        "consensus_zero": scores.count(0),
    }


def cross_question_summary(comparisons: dict, unblinded: dict, primary_pass: bool) -> dict:
    per_question = {}
    for question in ("S2", "S10"):
        ids = sorted(
            block_id for block_id, row in unblinded["blocks"].items()
            if row["question"] == question
        )
        counts = descriptive_score_summary([comparisons[block_id] for block_id in ids])
        counts["repetition_threshold_met"] = (
            counts["consensus_positive"] >= 3
            and counts["consensus_positive"] > counts["consensus_negative"]
        )
        per_question[question] = counts
    supported = primary_pass and all(
        row["repetition_threshold_met"] for row in per_question.values()
    )
    return {
        "eligible_only_if_primary_passes": primary_pass,
        "per_question": per_question,
        "repeated_across_both_questions": supported,
        "reporting_note": (
            "两道新题均达到登记的重复标准"
            if supported else "不得声称跨两题重复；必须并列两题计数"
        ),
    }


def primary_account_summary(rows: list[dict]) -> dict:
    methods = {}
    status_counts = {
        "direction": 0, "equal": 0, "measurement_failure": 0,
        "family_split": 0, "no_majority": 0,
    }
    cannot_count = 0
    denominator = len(rows) * 2 * len(c.ACCOUNTS)
    for method in ("menu", "open"):
        methods[method] = {}
        for account in c.ACCOUNTS:
            counts = {
                "M_more": 0, "N_more": 0, "equal": 0,
                "measurement_failure": 0, "family_split": 0, "no_majority": 0,
            }
            for row in rows:
                result = row["methods"][method]["accounts"][account]
                status = result["status"]
                status_counts[status] += 1
                if result["result"] == "无法判断":
                    cannot_count += 1
                if result["result"] == row["focal_label"]:
                    counts["M_more"] += 1
                elif result["result"] == row["reference_label"]:
                    counts["N_more"] += 1
                elif result["result"] == "相当":
                    counts["equal"] += 1
                elif status in counts:
                    counts[status] += 1
                else:
                    raise SystemExit(f"未覆盖的主账结果：{result}")
            methods[method][account] = counts

    joint_disagreement = 0
    account_disagreement = {account: 0 for account in c.ACCOUNTS}
    for row in rows:
        if row["methods"]["menu"]["score"] != row["methods"]["open"]["score"]:
            joint_disagreement += 1
        for account in c.ACCOUNTS:
            left = row["methods"]["menu"]["accounts"][account]["result"]
            right = row["methods"]["open"]["accounts"][account]["result"]
            if left != right:
                account_disagreement[account] += 1
    return {
        "methods": methods,
        "measurement_quality": {
            "group_account_denominator": denominator,
            "status_counts": status_counts,
            "cannot_judge_count": cannot_count,
            "cannot_judge_rate": cannot_count / denominator if denominator else 0.0,
        },
        "method_disagreement": {
            "joint_score_count": joint_disagreement,
            "joint_score_denominator": len(rows),
            "joint_score_rate": joint_disagreement / len(rows) if rows else 0.0,
            "per_account_counts": account_disagreement,
            "per_account_denominator": len(rows),
        },
        "warning": "单账只作描述，不得替代联合命中。",
    }


def decisive_evidence_location_audit(codings: dict, blinded: dict) -> list[dict]:
    rows = []
    for slot, questions in codings.items():
        for question, doc in questions.items():
            for block in doc["blocks"]:
                block_id = block["block_id"]
                for pair in c.PAIRS:
                    for account in c.ACCOUNTS:
                        verdict = block["comparisons"][pair][account]
                        if verdict["choice"] not in c.LABELS:
                            continue
                        decisive = verdict["decisive"]
                        answer = decisive["answer"]
                        location = c.locate_evidence(
                            blinded["blocks"][block_id]["answers"][answer],
                            decisive["evidence"], decisive["occurrence"],
                        )
                        rows.append({
                            "account": account, "answer": answer, "block_id": block_id,
                            "evidence": decisive["evidence"], "local_id": decisive["local_id"],
                            "location": location, "occurrence": decisive["occurrence"],
                            "pair": pair, "question": question, "slot": slot,
                            "sent_to_semantic_review": location is not None,
                            "failure_reason": None if location is not None else (
                                "精确匹配与仅移除 Markdown 强调标记后匹配均失败"
                            ),
                        })
    return rows


def run_aggregate() -> None:
    c.verify_run_authorization()
    for stage in ("sentinel", "generation", "coding", "review"):
        c.verify_stage_manifest(stage)
    codings = load_codings()
    blinded = c.load(RUN / "answers_blinded.json")
    reviews = review_index(codings, blinded)
    unblinded = c.load(RUN / "answers_unblinded.json")
    comparisons = {"M_vs_N": {}, "M_vs_G": {}, "G_vs_N": {}}
    arm_pairs = {"M_vs_N": ("M", "N"), "M_vs_G": ("M", "G"), "G_vs_N": ("G", "N")}
    for block_id, source in sorted(unblinded["blocks"].items()):
        for name, (focal, reference) in arm_pairs.items():
            comparisons[name][block_id] = summarize_pair(
                codings, reviews, source["question"], block_id,
                source["blind_mapping"], blinded["blocks"][block_id]["answers"],
                focal, reference,
            )

    primary_ids = sorted(
        block_id for block_id, row in unblinded["blocks"].items()
        if row["question"] in ("S2", "S10")
    )
    replication_ids = sorted(
        block_id for block_id, row in unblinded["blocks"].items() if row["question"] == "S8"
    )
    primary = sign_summary(
        [comparisons["M_vs_N"][bid] for bid in primary_ids],
        c.CONFIG["thresholds"]["primary_min_consensus_positive"],
    )
    primary_rows = [comparisons["M_vs_N"][bid] for bid in primary_ids]
    mg = sign_summary(
        [comparisons["M_vs_G"][bid] for bid in primary_ids],
        c.CONFIG["thresholds"]["primary_min_consensus_positive"],
    )
    mg_threshold_met = mg.pop("pass")
    sequence = c.fixed_sequence(primary["pass"], mg_threshold_met)
    mg["inferentially_tested"] = sequence["secondary_inferentially_tested"]
    mg["registered_threshold_met_descriptively"] = mg_threshold_met
    mg["pass"] = mg_threshold_met if sequence["secondary_inferentially_tested"] else None
    mg["specificity_supported"] = sequence["specificity_supported"]
    replication_scores = [comparisons["M_vs_N"][bid]["consensus"] for bid in replication_ids]
    replication = {
        "positive": replication_scores.count(1), "negative": replication_scores.count(-1),
        "zero": replication_scores.count(0),
    }
    replication["pass"] = (
        replication["positive"] >= c.CONFIG["thresholds"]["replication_min_positive"]
        and replication["negative"] <= c.CONFIG["thresholds"]["replication_negative_max"]
    )

    main_lengths = {
        arm: [unblinded["blocks"][bid]["char_lengths"][arm] for bid in primary_ids]
        for arm in ("N", "G", "M")
    }
    medians = {arm: statistics.median(values) for arm, values in main_lengths.items()}
    nonmath_m_less = nonmath_m_more = 0
    for bid in primary_ids:
        row = comparisons["M_vs_N"][bid]
        source = unblinded["blocks"][bid]
        _, m_label, n_label = c.blind_pair(source["blind_mapping"], "M", "N")
        results = [row["methods"][method]["accounts"]["nonmath_breadth"]["result"]
                   for method in ("menu", "open")]
        if results == [n_label, n_label]:
            nonmath_m_less += 1
        elif results == [m_label, m_label]:
            nonmath_m_more += 1
    length_alarm = c.length_entanglement_alarm(
        medians["M"], medians["N"], nonmath_m_less, nonmath_m_more,
        c.CONFIG["thresholds"]["length_shorter_alarm_fraction"],
    )

    summary = {
        "cross_question_repetition": cross_question_summary(
            comparisons["M_vs_N"], unblinded, primary["pass"]
        ),
        "descriptive_G_vs_N": descriptive_score_summary(
            [comparisons["G_vs_N"][bid] for bid in primary_ids]
        ),
        "identity_surface": identity_summary(codings, unblinded),
        "length": {
            "alarm": length_alarm, "main_arm_medians_unicode_chars": medians,
            "m_nonmath_less_blocks": nonmath_m_less,
            "m_nonmath_more_blocks": nonmath_m_more,
            "required_caveat": "不能排除回答整体变短造成的机械挤出" if length_alarm else None,
        },
        "primary_separate_accounts": primary_account_summary(primary_rows),
        "primary_M_vs_N": primary,
        "secondary_M_vs_G": mg,
        "registered_replication_S8": replication,
        "scope": "仅适用于冻结模型、通道、题目与背景注入方式；全部编码与复核均为 AI。",
    }
    c.dump(summary, RUN / "summary.json")
    c.dump({
        "comparisons": comparisons,
        "decisive_evidence_locations": decisive_evidence_location_audit(codings, blinded),
    }, RUN / "audit.json")
    c.enforce_request_limits()
    c.write_stage_manifest(
        "results",
        [
            RUN / "summary.json", RUN / "audit.json", RUN / "01_run_state.json",
            RUN / "manifest_review.json",
        ],
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    raise SystemExit(
        "正式分析 v2 禁止直接执行 legacy pipeline；"
        "只能使用 analysis_v2.py 按 prepare → calibrate → encode → review → aggregate 运行"
    )


if __name__ == "__main__":
    main()
