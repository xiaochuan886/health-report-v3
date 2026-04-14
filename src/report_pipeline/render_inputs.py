from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HEALTH_GUIDE_ITEMS = [
    # 第五部分 健康生活指南 - 防癌抗癌健康指南
    ("**一、认识癌症**\n"
     "\"癌症\"的英文名字cancer起源于拉丁文，直译是\"螃蟹\"。早在公元前400年，医学鼻祖希腊医生希波克拉底首先用这个词对器官组织的癌症做过记录。癌症就像螃蟹一样在身体里四处横行，疯狂地横扫并扩展它的地盘，直至将宿主组织吞噬消灭。19世纪德国生理学家穆勒博士发现，癌症是由大量的癌细胞聚集起来形成的。癌细胞与正常细胞大不相同，具有超强的分裂能力，非常\"饥饿\"地攫取组织中的营养而能快速地生长。\n"
     "癌症不是一朝一夕就形成的，我们的检测就是要在它无声无息的生成时，抓住它！人体细胞由正常变成异常的癌细胞，再聚集成实体肿瘤，继而再变成恶性癌肿，可分为癌变潜伏期和癌症期两个时期。癌细胞无限增殖和癌细胞转移，才是癌症名副其实的两大特征。"),
    ("**二、癌症风险通过科学的健康管理是可以控制并消除的**\n"
     "越来越多的科学证据清晰地表明癌症的风险是可以控制并被消除的，不是只靠医学上的突破或神奇的药物，而可以依靠科学的健康管理和生活方式的改变。美国国家卫生院（NIH）下属的国立癌症研究所（NCI）联合美国癌症研究所（AICR）自1983年以来一直致力于癌症预防的项目，在饮食、营养和防癌领域做了大量的开拓性工作。至今已有超过4500项的研究是饮食和防癌项目的组成部分。"),
    ("**三、癌症风险对策的一般原则**\n"
     "（1）保持愉悦的心态：查出癌症风险，不论结果报告是什么级别，都不是临床诊断的癌症，所以不要紧张，最忌讳惊恐、害怕和焦虑。长期不良情绪会使人体产生应激反应，过强的应激反应就会降低人体免疫力，使癌细胞有可乘之机。\n"
     "（2）保持癌细胞-免疫力的平衡：正常人体内每天都有细胞分裂生成的癌细胞分散存在于器官组织之中。癌细胞不断地生成，又不断地被自身的免疫系统消灭，这种动态平衡保持了人的健康。有了风险说明癌细胞的生成比自身免疫力占了优势，所以控制风险最重要的对策是增强自身免疫力。\n"
     "2015年，美国癌症研究学会(AACR)年报总结出生活中最常见的免疫力五大杀手：a)运动不足或不正确；b)营养不足或不正确；c)抑郁、精神压力大的不良情绪；d)吸烟、滥用药物、长期熬夜；e)缺乏和谐而充满爱的家庭生活。"),
    ("**四、运动健身，能防癌吗？**\n"
     "能！运动的确是防癌\"神器\"。因为癌症是一种\"能量\"疾病，能量在癌细胞激活过程中扮演着重要的角色，同时能量又是维护正常细胞生命周期所必须。健康的关键就是维持能量的平衡。超重、肥胖以及过多的能量供应都会促使细胞发生癌变。因为运动会燃烧更多的卡路里，不但能瘦身减肥，还能改变情绪状态，运动常常是治疗忧郁的最佳方式。跑步给我们带来的那种幸福、自由和能量充沛的感觉不仅仅是内啡肽的作用，还受到一种重要的神经递质--多巴胺的影响。有研究证明，那些进行适量体育运动的人群来说，患某些癌症如乳腺癌、结肠癌、子宫内膜癌和晚期前列腺癌的风险会更低。\n"
     "建议：日常保持在热量摄入和运动之间维持平衡；成年人要在日常活动的基础上每周至少5天每天至少30分钟参加中强度的有氧运动（要出汗，但切忌大汗淋漓，切忌呼哧带喘）。"),
    ("**五、服用营养保健品、复合维生素有助于防癌吗？**\n"
     "有！但要坚持长期适量服用。许多维生素都是抗氧化剂，对保护自身组织免受自由基（氧化）所导致的持续性损害。由于这种损害可增加癌症风险，所以某些抗氧化剂可能会有助于预防癌症。例如维生素C、维生素E、类胡萝卜素（如β-胡萝卜素和维生素A）和其他植物化学物质。研究显示，多食用富含维生素和抗氧化剂物质的蔬菜和水果会降低人们患某些癌症的风险。\n"
     "叶酸是一种天然的B族维生素，缺乏叶酸可能会增加人们患结直肠癌和乳腺癌的风险，对饮酒人群来说尤其如此。硒补充剂可能会降低人们患肺癌、结肠癌和前列腺癌的风险，但服用硒补充剂的最高剂量不应超过200微克每天。高钙食物可能有助于降低结直肠癌风险，但摄入过多的钙可增加人们患前列腺癌的风险。男性应主要通过食物来摄入推荐剂量而非过量的钙质。"),
    ("**六、Science重大发现：1天1包烟有多可怕？每年150个基因突变！**\n"
     "来自英国WellcomeTrust Sanger研究所、美国Los Alamos国家实验室等机构的科学家们发现，每天吸一包烟的\"吸烟者\"每年每个肺细胞中会累积平均150个额外突变。2016年11月4日发表在Science杂志上的这一研究提供了吸烟数量与肿瘤DNA中突变数量之间的直接关联。其中，肺癌中观察到的突变率最高，但身体其它部分的肿瘤中也包含了这些吸烟相关的突变。\n"
     "癌症预防的最新研究成果（14,641受试者），长期服用复合维生素及矿物质可以降低23%的癌症发生率。\n"
     "警惕无形杀手\"二手烟\"：除了主动吸烟者，世界上还有很多受二手烟危害的人。研究指出，中国有近7.4亿人每天暴露于二手烟雾危害之下，其中1.82亿为儿童。"),
    ("**七、饮酒会增加患癌风险吗？**\n"
     "会！饮酒会增加人们患口腔癌、咽癌、喉癌、食管癌、肝癌、乳腺癌、结肠癌和直肠癌的风险。饮酒人士应该限制酒的摄入量，男士每天饮酒不宜超过2酒精单位，女士不超过1酒精单位。1酒精单位相当于360ml啤酒、150ml的葡萄酒、或者45ml 40度烈性酒。对某些癌症而言，同时饮酒并吸烟所增加的患癌风险远高于只饮酒或只吸烟的风险。规律的饮酒，即便每周的饮酒量很少，也可增加女性患乳腺癌的风险。乳腺癌高危女性群体可以考虑戒酒。"),
    ("**八、膳食纤维能降低癌症风险吗？**\n"
     "能！膳食纤维是指多种人体不能消化的植物性碳水化合物。干燥豆类、蔬菜、全谷类和水是膳食纤维的优质来源。膳食纤维可进一步分为\"可溶的\"（比如燕麦麸、豌豆、豆类和洋车前子纤维），和\"不可溶的\"（比如小麦麸、水果皮、坚果、种子和纤维素）。最新研究表明，膳食纤维可降低某些癌症的风险，尤其是结直肠癌。因此，ACS建议人们食用全谷类、蔬菜和水等高纤维食物来帮助降低癌症风险。"),
    ("**九、大豆制品能降低癌症风险吗？**\n"
     "和其他豆科植物一样，大豆及大豆制品是蛋白质的优质来源以及肉类的有益替代品。大豆含有多种植物化学物质，其中包括异黄酮。大豆中的植物化学物质具有微弱的雌激素样活性，并可能有助于预防激素依赖性癌症。有越来越多的证据表明食用传统大豆制品比如豆腐可能会降低人们患乳腺癌、前列腺癌或子宫内膜癌的风险。也有一些证据表明食用传统大豆制品可能还会降低人们患某些其他癌症的风险。"),
    ("**十、大蒜能降低癌症风险吗？**\n"
     "大蒜和其他葱属植物中含有的葱属植物化合物对健康有益。针对大蒜能否降低癌症风险的研究正在进行，一些研究表明大蒜可以降低结直肠癌的风险。大蒜和其他葱属植物可以被列到能够降低癌症风险的推荐蔬菜目录当中。目前尚没有充足证据证明葱属植物化合物补充剂能降低癌症风险。"),
    ("**十一、肥胖会增加癌症风险吗？**\n"
     "会。超重或肥胖与人们更高的乳腺癌（绝经后女性）、结直肠癌、子宫内膜癌、食道癌、肾癌、胰腺癌、胆囊癌（可能）患癌风险有关。肥胖也可能与人们更高的肝癌、宫颈癌、卵巢癌以及非霍奇金淋巴瘤、多发性骨髓瘤和侵袭性前列腺癌的患癌风险有关。\n"
     "虽然对减肥是否会降低癌症风险的研究有限，但是一些研究表明，减肥会降低绝经后女性患乳腺癌和其他癌症的风险。成年人避免过度的体重增加也是十分重要的，因为这不仅可能会降低患癌风险，还可能会降低他们患其他慢性疾病的风险。"),
    ("**十二、喝茶（红茶或绿茶）能降低癌症风险吗？**\n"
     "茶是一种饮料，茶树的叶子、嫩芽或细枝均可泡制成茶。红茶、绿茶、白茶、普洱茶和其他各种类型的茶均来自于同一棵茶树，但是它们反映了不同的加工方式。一些研究人员提出，茶之所以会预防癌症是因为茶含有抗氧化剂、多元酚和类黄酮。动物研究已证明有些茶（包括绿茶）可降低癌症风险，但是人类研究发现的结果喜忧参半。虽然实验室研究结果一直令人满意，而且喝茶也是许多美食的一部分，但是目前的证据尚不能证明喝茶是降低癌症风险的主要原因。"),
    ("**十三、多吃抗癌食物就能防癌？**\n"
     "肿瘤与饮食有着千丝万缕的关系，健康饮食更是对抗癌症的有效措施之一。\"吃什么能防癌？\"家庭医生在线肿瘤频道的咨询帖中不少网友都有此疑问。国外有很多探索食物中\"抗癌物质\"的实验，发现了不少具有\"抗癌物质\"的\"抗癌食物\"，如包菜等十字花科植物、番茄等等。但肿瘤的发生是多种因素综合作用的结果，饮食仅是其中一个方面；另外，食物进入人体还有一个非常复杂的代谢过程，受多种因素影响，这些\"抗癌食物\"或许对身体有一定的好处，但具体有何效用、效用大小却并未可知。为此，寄望于多吃某些食物能预防癌症的想法是不科学的。"),
    # 预防心脑血管疾病风险
    ("**十四、食品宜与忌**\n"
     "①食物多样、搭配合理：碳水化合物50-60%；蛋白质10-15%；脂肪20-30%，平均每天需要12种以上，每周需要25种以上食物。\n"
     "②吃动平衡、健康体重：每周至少5天中等强度运动，累积150分钟，每天走6000步以上；减少久坐时间。\n"
     "③多吃蔬果、奶类、全谷物和大豆：强调摄入全谷物，减少精细谷类，常吃大豆制品和坚果，每天摄入300g新鲜蔬菜，其中深色蔬菜占1/2，每天摄入200-350g新鲜水果。\n"
     "④适量吃鱼、禽、蛋、瘦肉：每天平均3-4两鱼禽肉蛋类、每周吃2次鱼，每天一个鸡蛋（不弃蛋黄），少吃肥肉、烟熏肉和腌制肉。\n"
     "⑤少油少盐，控糖限酒：每日盐摄入量小于5g，每日酒精摄入量小于15g。\n"
     "⑥规律进餐，足量饮水：每日饮水量1500-1700ml，主动饮水，少量多次，推荐白水和茶水；少喝、不喝含糖饮料。"),
    ("**十五、膳食宝塔**\n"
     "第一层：谷类200~300克，其中包括全谷物和杂豆50~150克；薯类50~100克。\n"
     "第二层：蔬菜类300~500克，水果类200~350克（深色蔬菜占1/2）。\n"
     "第三层：动物性食物120~200克，每周至少2次水产品，每天一个鸡蛋。\n"
     "第四层：奶及奶制品300~500克，大豆及坚果类25~35克。\n"
     "第五层：盐＜5克，油25~30克。\n"
     "《黄帝内经》记载：\"五谷为养，五果为助，五畜为益，五菜为充\"，充分体现谷类食物的重要性。"),
    ("**十六、体育锻炼宜与忌**\n"
     "适宜运动：步行（每天30分钟左右）、太极拳、慢跑、游泳、骑自行车等，量力而行，持之以恒。\n"
     "不宜做剧烈活动：如快跑、快节奏的舞蹈等。如果出现\"呼哧带喘\"的情况，说明已有心脑组织缺氧，陡然增加心梗或脑梗的风险，一定要避免。\n"
     "不宜清晨锻炼：上午6时至9时是冠心病和脑出血发作最危险的时刻，应避开心血管事件\"高峰期\"，将时间安排在下午及傍晚进行。"),
    ("**十七、生活习惯宜与忌**\n"
     "适宜的习惯：劳逸结合，保证充足睡眠；生活规律，养成健康的生活习惯；心胸开阔，心情愉快。\n"
     "应忌的习惯：戒酒，避免精神紧张、情绪激动和过度劳累，减少烦恼焦虑。"),
    ("**十八、老年人预防心梗和脑梗须知**\n"
     "年纪大了床头放三样东西，必要时可救命：1瓶水，2颗阿司匹林和急救电话。\n"
     "夜间睡前喝250ml温热白开水。据统计，心梗患者绝大部分是清晨起床时被发现的，猝发时间多在半夜。老年人在夜间喝一杯白开水，有助于预防中风和心梗的发生。\n"
     "每天喝绿茶：北京大学医学院研究发现每天喝绿茶一杯以上的人发生心梗的可能性减少42%。\n"
     "出现心梗或脑梗的前驱不适征象，要立即嚼服300毫克阿司匹林，可起到抗凝血的作用。"),
    ("**十九、对已提示异常或接近临界的指标，建议结合临床情况定期复查。**"),
]

HEALTH_GUIDE_IMAGES = [
    {
        "path": "health_guide_images/page21_decompressed.png",
        "caption": "图1：维生素与癌症预防关系"
    },
    {
        "path": "health_guide_images/page24.jpg",
        "caption": "图2：膳食宝塔"
    },
]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_record(records: list[dict]) -> dict:
    return records[0] if records else {}


def _clean(value: Any, default: str = "--") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def load_render_bundle(input_dir: str | Path) -> dict[str, Any]:
    base = Path(input_dir)
    cancer_interp_path = base / "cancer_interpretations.json"
    cardio_interp_path = base / "cardio_interpretations.json"
    personal_info_path = base / "personal_info.json"
    quality_control_path = base / "quality_control.json"
    return {
        "input_dir": str(base),
        "matched_rows": _read_json(base / "matched_indicators.json"),
        "summary_sections": _read_json(base / "summary_sections.json"),
        "nutrition_sections": _read_json(base / "nutrition_sections.json"),
        "cancer_interpretations": _read_json(cancer_interp_path) if cancer_interp_path.exists() else [],
        "cardio_interpretations": _read_json(cardio_interp_path) if cardio_interp_path.exists() else [],
        "personal_info": _read_json(personal_info_path) if personal_info_path.exists() else {},
        "quality_control": _read_json(quality_control_path) if quality_control_path.exists() else {},
    }


def build_render_context(bundle: dict[str, Any]) -> dict[str, Any]:
    matched_rows = bundle["matched_rows"]
    summary_sections = bundle["summary_sections"]
    nutrition_sections = bundle["nutrition_sections"]
    cancer_interpretations = bundle.get("cancer_interpretations", [])
    first = _first_record(matched_rows)

    cancer_summary_rows = summary_sections.get("癌症健康监测小结", [])
    # Part 2 needs ALL matched cancer indicators (not filtered by abnormal status)
    # matched_rows has exploded disease types, deduplicate by (raw_code, indicator_short_name)
    seen_cancer: set[tuple[str, str]] = set()
    cancer_all_rows = []
    for row in matched_rows:
        if row.get("risk_category") == "癌筛" and row.get("match_status") != "unmatched":
            key = (row.get("indicator_short_name", ""), row.get("raw_code", ""))
            if key[0] and key not in seen_cancer:
                seen_cancer.add(key)
                cancer_all_rows.append(row)
    cardio_rows = summary_sections.get("心脑血管健康监测小结", [])
    # Part 3 needs ALL matched cardio indicators (not filtered by abnormal status)
    seen_cardio: set[tuple[str, str]] = set()
    cardio_all_rows = []
    for row in matched_rows:
        if row.get("risk_category") == "心筛" and row.get("match_status") != "unmatched":
            key = (row.get("indicator_short_name", ""), row.get("raw_code", ""))
            if key[0] and key not in seen_cardio:
                seen_cardio.add(key)
                cardio_all_rows.append(row)
    cardio_all_rows.sort(key=lambda r: r.get("display_order") or 999)

    glossary_map: dict[str, dict[str, str]] = {}
    glossary_source_rows = list(cancer_all_rows)
    glossary_source_rows.extend(cardio_all_rows)

    for row in glossary_source_rows:
        short_name = _clean(row.get("indicator_short_name"), default="")
        if not short_name or short_name in glossary_map:
            continue
        label = _clean(row.get("indicator_label"))
        # Skip if indicator_label is "--" (no interpretation data available)
        if label == "--":
            continue
        glossary_map[short_name] = {
            "indicator_short_name": short_name,
            "indicator_label": label,
            "indicator_meaning": _clean(row.get("indicator_meaning")),
            "indicator_application": _clean(row.get("indicator_application")),
        }

    cardio_interpretations = bundle.get("cardio_interpretations", [])
    personal_info = bundle.get("personal_info", {})

    # 一般普通检查
    general_check = {
        "身高": personal_info.get("身高"),
        "体重": personal_info.get("体重"),
        "腹围": personal_info.get("腹围"),
        "收缩压": personal_info.get("收缩压"),
        "舒张压": personal_info.get("舒张压"),
        "脉搏": personal_info.get("脉搏"),
        "BMI": personal_info.get("BMI"),
        "腰高比": personal_info.get("腰高比"),
    }

    # 大营养板块小结 - 筛选异常的微量元素和维生素指标
    abnormal_nutrition: list[dict] = []
    for row in nutrition_sections.get("微量元素检测结果", []):
        risk_status = _clean(row.get("risk_status"))
        if risk_status and risk_status not in {"normal", "正常", ""}:
            abnormal_nutrition.append({**row, "category": "微量元素"})
    for row in nutrition_sections.get("维生素检测结果", []):
        risk_status = _clean(row.get("risk_status"))
        if risk_status and risk_status not in {"normal", "正常", ""}:
            abnormal_nutrition.append({**row, "category": "维生素"})

    return {
        "title": "综合健康检测报告",
        "patient_name": _clean(first.get("病人姓名")),
        "patient_gender": _clean(first.get("病人性别")),
        "patient_age": _clean(first.get("病人年龄")),
        "specimen_type": _clean(first.get("specimen_type")),
        "received_at": _clean(first.get("received_at")),
        "reported_at": _clean(first.get("reported_at")),
        "hospital_name": _clean(first.get("送检医院")),
        "summary_sections": summary_sections,
        "cancer_summary_rows": cancer_summary_rows,
        "cancer_all_rows": cancer_all_rows,
        "cardio_rows": cardio_rows,
        "cardio_all_rows": cardio_all_rows,
        "cancer_interpretations": cancer_interpretations,
        "cardio_interpretations": cardio_interpretations,
        "nutrition_sections": nutrition_sections,
        "nutrition_explanations": {
            "微量元素检测结果": [
                row
                for row in nutrition_sections.get("微量元素检测结果", [])
                if _clean(row.get("indicator_meaning")) != "--" or _clean(row.get("indicator_application")) != "--"
            ],
            "维生素检测结果": [
                row
                for row in nutrition_sections.get("维生素检测结果", [])
                if _clean(row.get("indicator_meaning")) != "--" or _clean(row.get("indicator_application")) != "--"
            ],
        },
        "general_check": general_check,
        "nutrition_summary": abnormal_nutrition,
        "quality_control": bundle.get("quality_control", {}),
        "glossary_rows": list(glossary_map.values()),
        "health_guide_items": HEALTH_GUIDE_ITEMS,
        "health_guide_images": HEALTH_GUIDE_IMAGES,
        "health_guide_path": str(Path(bundle.get("input_dir", "")) / "health_guide.md"),
    }
