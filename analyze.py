"""读取 competitor_template.xlsx，做情感分析 + 关键词提取 + 生成报告。

用法:
    python analyze.py                       # 读默认文件，输出 report/
    python analyze.py my_data.xlsx out_dir  # 指定输入输出
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import jieba
import jieba.analyse
import pandas as pd
from snownlp import SnowNLP

# 情感分数阈值: SnowNLP 输出 0-1, 越大越正面
POSITIVE_THRESHOLD = 0.6
NEGATIVE_THRESHOLD = 0.4

# 停用词（评价里常见的无意义词）
STOPWORDS = {
    "宝贝", "东西", "卖家", "买家", "商品", "店家", "客服", "物流", "快递",
    "收到", "购买", "下单", "评价", "确实", "感觉", "觉得", "应该", "可能",
    "一下", "一个", "什么", "怎么", "这样", "那样", "现在", "已经", "还是",
    "就是", "还有", "没有", "可以", "不错", "知道", "看到", "一直", "比较",
    "真的", "非常", "特别", "十分", "很多", "一些", "这个", "那个", "我们",
    "你们", "他们", "自己", "时候", "时间", "今天", "昨天", "明天",
}


@dataclass
class ProductStat:
    idx: int
    title: str
    shop: str
    price: float | None
    monthly_sales: str
    total_reviews: str
    claimed_pos_rate: float | None
    reviews: list[str] = field(default_factory=list)
    pos_count: int = 0
    neu_count: int = 0
    neg_count: int = 0
    avg_sentiment: float = 0.0
    pos_keywords: list[tuple[str, float]] = field(default_factory=list)
    neg_keywords: list[tuple[str, float]] = field(default_factory=list)
    sample_neg: list[str] = field(default_factory=list)

    @property
    def review_count(self) -> int:
        return len(self.reviews)

    @property
    def calc_pos_rate(self) -> float:
        if self.review_count == 0:
            return 0.0
        return self.pos_count / self.review_count * 100


def classify(text: str) -> tuple[str, float]:
    """返回 (好评/中评/差评, 情感分数)。"""
    text = (text or "").strip()
    if not text:
        return "中评", 0.5
    try:
        score = SnowNLP(text).sentiments
    except Exception:
        score = 0.5
    if score >= POSITIVE_THRESHOLD:
        return "好评", score
    if score <= NEGATIVE_THRESHOLD:
        return "差评", score
    return "中评", score


def extract_keywords(texts: list[str], topk: int = 15) -> list[tuple[str, float]]:
    if not texts:
        return []
    blob = "\n".join(texts)
    raw = jieba.analyse.extract_tags(blob, topK=topk * 2, withWeight=True)
    return [(w, round(s, 3)) for w, s in raw if w not in STOPWORDS and len(w) > 1][:topk]


def load_products(xlsx_path: Path) -> list[ProductStat]:
    summary = pd.read_excel(xlsx_path, sheet_name="竞品总表", header=0, skiprows=[1])
    products: list[ProductStat] = []

    for _, row in summary.iterrows():
        idx = row.get("序号")
        if pd.isna(idx):
            continue
        idx = int(idx)
        sheet_name = f"P{idx:02d}_评价"
        try:
            rev_df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=1, skiprows=[2])
        except ValueError:
            rev_df = pd.DataFrame(columns=["评价类型", "评价内容"])

        p = ProductStat(
            idx=idx,
            title=str(row.get("商品标题", "") or ""),
            shop=str(row.get("店铺名", "") or ""),
            price=_to_float(row.get("价格(元)")),
            monthly_sales=str(row.get("月销量(件)", "") or ""),
            total_reviews=str(row.get("累计评价数", "") or ""),
            claimed_pos_rate=_to_float(row.get("好评率(%)")),
        )

        for _, r in rev_df.iterrows():
            content = r.get("评价内容")
            if pd.isna(content) or not str(content).strip():
                continue
            p.reviews.append(str(content).strip())

        products.append(p)

    return products


def _to_float(v) -> float | None:
    if pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def analyze(p: ProductStat, manual_types: list[str] | None = None) -> None:
    pos_texts, neg_texts = [], []
    scores = []
    for i, text in enumerate(p.reviews):
        manual = (manual_types[i].strip() if manual_types and i < len(manual_types) and isinstance(manual_types[i], str) else "")
        if manual in ("好评", "中评", "差评"):
            label = manual
            score = {"好评": 0.8, "中评": 0.5, "差评": 0.2}[label]
        else:
            label, score = classify(text)
        scores.append(score)
        if label == "好评":
            p.pos_count += 1
            pos_texts.append(text)
        elif label == "差评":
            p.neg_count += 1
            neg_texts.append(text)
        else:
            p.neu_count += 1

    p.avg_sentiment = round(sum(scores) / len(scores), 3) if scores else 0.0
    p.pos_keywords = extract_keywords(pos_texts)
    p.neg_keywords = extract_keywords(neg_texts)
    p.sample_neg = neg_texts[:5]


def write_report(products: list[ProductStat], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 汇总 CSV
    rows = []
    for p in products:
        rows.append({
            "序号": p.idx,
            "商品标题": p.title,
            "店铺": p.shop,
            "价格": p.price,
            "月销量": p.monthly_sales,
            "累计评价": p.total_reviews,
            "页面好评率%": p.claimed_pos_rate,
            "抽样评价数": p.review_count,
            "好评数": p.pos_count,
            "中评数": p.neu_count,
            "差评数": p.neg_count,
            "实测好评率%": round(p.calc_pos_rate, 1),
            "平均情感分": p.avg_sentiment,
            "TOP3好评词": " / ".join(w for w, _ in p.pos_keywords[:3]),
            "TOP3差评词": " / ".join(w for w, _ in p.neg_keywords[:3]),
        })
    df = pd.DataFrame(rows)
    csv_path = out_dir / "summary.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 2) Markdown 报告
    md = ["# 竞品评价分析报告", ""]
    md.append(f"共分析 **{len(products)}** 个商品，"
              f"抽样评价 **{sum(p.review_count for p in products)}** 条。")
    md.append("")
    md.append("## 一、销量与口碑总览")
    md.append("")
    md.append("| # | 标题 | 月销 | 抽样 | 好评率 | 情感分 |")
    md.append("|---|---|---|---|---|---|")
    for p in products:
        title = (p.title[:30] + "…") if len(p.title) > 30 else p.title
        md.append(
            f"| {p.idx} | {title} | {p.monthly_sales} | "
            f"{p.review_count} | {p.calc_pos_rate:.1f}% | {p.avg_sentiment} |"
        )
    md.append("")

    md.append("## 二、全市场差评关键词 TOP20")
    all_neg = []
    for p in products:
        for w, _ in p.neg_keywords:
            all_neg.append(w)
    cnt = Counter(all_neg).most_common(20)
    md.append("")
    md.append("| 关键词 | 出现在几个商品 |")
    md.append("|---|---|")
    for w, c in cnt:
        md.append(f"| {w} | {c} |")
    md.append("")
    md.append("> 👉 这些是**整个品类的共性槽点**，你做产品时优先规避。")
    md.append("")

    md.append("## 三、每个商品详细分析")
    for p in products:
        md.append(f"\n### P{p.idx:02d} · {p.title}")
        md.append(f"- 店铺: {p.shop} | 价格: {p.price} | 月销: {p.monthly_sales}")
        md.append(f"- 评价分布: 好评 {p.pos_count} / 中评 {p.neu_count} / 差评 {p.neg_count}")
        md.append(f"- 实测好评率 **{p.calc_pos_rate:.1f}%**，平均情感分 **{p.avg_sentiment}**")
        if p.claimed_pos_rate is not None and p.review_count >= 10:
            gap = p.claimed_pos_rate - p.calc_pos_rate
            if abs(gap) > 15:
                md.append(f"- ⚠️ 页面好评率({p.claimed_pos_rate}%)与实测差距 {gap:+.1f}%，"
                          f"可能存在刷评 / 差评折叠")
        md.append(f"- 👍 好评关键词: {', '.join(w for w, _ in p.pos_keywords[:8]) or '无'}")
        md.append(f"- 👎 差评关键词: {', '.join(w for w, _ in p.neg_keywords[:8]) or '无'}")
        if p.sample_neg:
            md.append("- 差评样本:")
            for s in p.sample_neg:
                md.append(f"  - > {s[:120]}")

    md.append("")
    md.append("## 四、行动建议")
    md.append("")
    if cnt:
        top3 = "、".join(w for w, _ in cnt[:3])
        md.append(f"1. 品类前三大共性槽点是 **{top3}**，新品设计/选品时重点优化")
    sorted_by_score = sorted(products, key=lambda x: x.avg_sentiment, reverse=True)
    if sorted_by_score:
        md.append(f"2. 口碑最好的是 **P{sorted_by_score[0].idx:02d}**（情感分 {sorted_by_score[0].avg_sentiment}），"
                  "建议研究其好评关键词作为卖点参考")
        md.append(f"3. 口碑最差的是 **P{sorted_by_score[-1].idx:02d}**（情感分 {sorted_by_score[-1].avg_sentiment}），"
                  "差评内容可作为竞品攻击点 / 自身规避项")

    md_path = out_dir / "report.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"✅ 报告已生成:")
    print(f"  - {csv_path}")
    print(f"  - {md_path}")


def main():
    args = sys.argv[1:]
    xlsx = Path(args[0]) if args else Path(__file__).parent / "competitor_template.xlsx"
    out = Path(args[1]) if len(args) > 1 else Path(__file__).parent / "report"

    if not xlsx.exists():
        sys.exit(f"找不到文件: {xlsx}\n请先运行 `python make_template.py` 生成模板，并填入数据。")

    print(f"读取: {xlsx}")
    products = load_products(xlsx)
    print(f"载入 {len(products)} 个商品")

    for p in products:
        if p.review_count == 0:
            print(f"  P{p.idx:02d} 无评价数据，跳过")
            continue
        analyze(p)
        print(f"  P{p.idx:02d} ✓ {p.review_count} 条 → "
              f"好{p.pos_count} 中{p.neu_count} 差{p.neg_count}")

    write_report([p for p in products if p.review_count > 0], out)


if __name__ == "__main__":
    main()
