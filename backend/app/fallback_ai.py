import re
from typing import Dict, List

from app.schemas import CandidateProfile, JDProfile
from app.text_utils import INDUSTRY_TERMS, extract_max_years, extract_skills, split_sentences, unique_preserve_order


def extract_jd_profile(text: str) -> JDProfile:
    sentences = split_sentences(text)
    first = sentences[0] if sentences else "未命名岗位"
    job_title = _clean_title(first)
    skills = extract_skills(text)
    responsibilities = [
        sentence
        for sentence in sentences
        if any(keyword in sentence for keyword in ("负责", "职责", "建设", "开发", "搭建", "优化"))
    ][:6]
    if not responsibilities and sentences:
        responsibilities = sentences[:3]
    hard_requirements = [
        sentence
        for sentence in sentences
        if any(keyword in sentence for keyword in ("本科", "硕士", "博士", "学历", "证书", "必须", "硬性"))
    ][:5]
    industry = _extract_industry(text)
    seniority = _extract_seniority(text)
    required = skills[:6]
    nice = skills[6:10]
    return JDProfile(
        job_title=job_title,
        responsibilities=responsibilities,
        required_skills=required,
        nice_to_have_skills=nice,
        seniority=seniority,
        years_required=extract_max_years(text),
        industry_background=industry,
        hard_requirements=hard_requirements,
    )


def extract_candidate_profile(text: str, source_name: str = "简历") -> CandidateProfile:
    sentences = split_sentences(text)
    name = _extract_name(text, source_name)
    contacts = _extract_contacts(text)
    education = [
        sentence
        for sentence in sentences
        if any(keyword in sentence for keyword in ("大学", "学院", "本科", "硕士", "博士", "专科", "MBA"))
    ][:5]
    work = [
        sentence
        for sentence in sentences
        if ("年" in sentence and any(keyword in sentence for keyword in ("经验", "工作", "开发", "运营", "负责")))
        or "工作经历" in sentence
    ][:6]
    projects = [
        sentence
        for sentence in sentences
        if any(keyword in sentence for keyword in ("项目", "平台", "系统", "负责", "参与", "搭建", "建设"))
    ][:8]
    certifications = [sentence for sentence in sentences if any(keyword in sentence for keyword in ("证书", "认证"))][:4]
    highlights = [
        sentence
        for sentence in sentences
        if any(keyword in sentence for keyword in ("主导", "搭建", "优化", "提升", "从0到1", "负责"))
    ][:5]
    ambiguous = _ambiguous_points(text, projects, work)
    return CandidateProfile(
        name=name,
        contacts=contacts,
        education=education,
        work_experiences=work,
        projects=projects,
        skills=extract_skills(text),
        certifications=certifications,
        highlights=highlights,
        risk_points=[],
        ambiguous_points=ambiguous,
    )


def _clean_title(text: str) -> str:
    title = re.split(r"[，,。；;:：]", text)[0].strip()
    title = re.sub(r"^(岗位|职位|招聘)[:：\s]*", "", title)
    return title[:40] or "未命名岗位"


def _extract_seniority(text: str) -> str:
    for word in ("专家", "资深", "高级", "中级", "初级", "负责人", "主管"):
        if word in text:
            return word
    return "未说明"


def _extract_industry(text: str) -> List[str]:
    found = [term for term in INDUSTRY_TERMS if term.lower() in text.lower()]
    if "RAG" in found and "AI" not in found:
        found.append("AI")
    return unique_preserve_order(found)


def _extract_name(text: str, source_name: str) -> str:
    explicit = re.search(r"(?:姓名|候选人)[:：\s]*([\u4e00-\u9fa5]{2,5})", text)
    if explicit:
        return explicit.group(1)
    for line in text.splitlines()[:5]:
        stripped = line.strip()
        if re.fullmatch(r"[\u4e00-\u9fa5]{2,5}", stripped):
            return stripped
    stem = re.sub(r"\.(pdf|docx|txt)$", "", source_name, flags=re.IGNORECASE)
    return stem if stem and stem != "简历" else "未知候选人"


def _extract_contacts(text: str) -> Dict[str, str]:
    contacts: Dict[str, str] = {}
    phone = re.search(r"(?<!\d)(?:\+?86[-\s]?)?(1[3-9]\d{9})(?!\d)", text)
    email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    wechat = re.search(r"(?:微信|wechat|WeChat|WX|wx)[:：\s]*([A-Za-z][A-Za-z0-9_-]{5,})", text)
    if phone:
        contacts["phone"] = phone.group(1)
    if email:
        contacts["email"] = email.group(0)
    if wechat:
        contacts["wechat"] = wechat.group(1)
    return contacts


def _ambiguous_points(text: str, projects: List[str], work: List[str]) -> List[str]:
    points = []
    if projects and not re.search(r"(提升|降低|增长|QPS|DAU|%|\d+\s*(人|万|%|倍))", text):
        points.append("项目结果指标和业务影响未量化")
    if projects and not any(keyword in text for keyword in ("主导", "负责人", "owner", "Owner")):
        points.append("项目中的个人职责边界不够明确")
    if work and not re.search(r"20\d{2}|19\d{2}", text):
        points.append("关键工作经历的起止时间未说明")
    if not projects:
        points.append("缺少可深挖的项目经历描述")
    return unique_preserve_order(points)[:5]

