import json
from pathlib import Path
from typing import Iterable, Optional

from app.schemas import AgentSkill, AgentSkillCategory, JDProfile


INTERVIEW_DIRECTION_SKILL_IDS: dict[str, str] = {
    "AI Agent 开发": "ai-agent-dev",
    "算法与数据结构": "algorithm",
    "前端工程": "frontend",
    "Java 后端开发": "java-backend",
    "Python 后端开发": "python-backend",
    "系统设计": "system-design",
    "自定义 JD": "custom-jd",
}


class SkillRepository:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = Path(skills_dir)
        self._skills = self._load_skills()

    @classmethod
    def default(cls) -> "SkillRepository":
        return cls(Path(__file__).resolve().parents[2] / "skills")

    def list_skills(self) -> list[AgentSkill]:
        return list(self._skills.values())

    def get(self, skill_id: str) -> AgentSkill:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise KeyError(f"Unknown skill: {skill_id}") from exc

    def get_optional(self, skill_id: str) -> Optional[AgentSkill]:
        return self._skills.get(skill_id)

    def _load_skills(self) -> dict[str, AgentSkill]:
        if not self.skills_dir.exists():
            return {}
        skills: dict[str, AgentSkill] = {}
        for skill_dir in sorted(path for path in self.skills_dir.iterdir() if path.is_dir()):
            metadata_path = skill_dir / "skill.json"
            body_path = skill_dir / "SKILL.md"
            if not metadata_path.is_file() or not body_path.is_file():
                continue
            with metadata_path.open(encoding="utf-8") as file:
                metadata = json.load(file)
            categories = [
                AgentSkillCategory.model_validate(item)
                for item in metadata.get("categories", [])
            ]
            skill = AgentSkill(
                id=metadata.get("id") or skill_dir.name,
                name=metadata["name"],
                description=metadata.get("description", ""),
                keywords=metadata.get("keywords", []),
                categories=categories,
                question_focuses=metadata.get("question_focuses", []),
                rubric_focuses=metadata.get("rubric_focuses", []),
                followup_style=metadata.get("followup_style", ""),
                body=body_path.read_text(encoding="utf-8").strip(),
            )
            skills[skill.id] = skill
        return skills


def select_skills_for_jd(jd_profile: JDProfile, repository: SkillRepository) -> list[AgentSkill]:
    skills = repository.list_skills()
    if not skills:
        return []
    haystack = _normalize_search_text(
        [
            jd_profile.job_title,
            jd_profile.seniority,
            *jd_profile.required_skills,
            *jd_profile.nice_to_have_skills,
            *jd_profile.responsibilities,
            *jd_profile.hard_requirements,
        ]
    )
    scored: list[tuple[int, AgentSkill]] = []
    for skill in skills:
        score = _keyword_score(haystack, skill.keywords)
        if score > 0:
            scored.append((score, skill))
    if scored:
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [scored[0][1]]
    custom = repository.get_optional("custom-jd")
    return [custom] if custom is not None else [skills[0]]


def select_skill_for_direction(
    direction: str,
    repository: SkillRepository,
    jd_profile: Optional[JDProfile] = None,
) -> AgentSkill:
    normalized_direction = (direction or "").strip()
    mapped_skill_id = INTERVIEW_DIRECTION_SKILL_IDS.get(normalized_direction)
    if mapped_skill_id:
        skill = repository.get_optional(mapped_skill_id)
        if skill is not None:
            return skill

    if jd_profile is not None:
        selected = select_skills_for_jd(jd_profile, repository)
        if selected:
            return selected[0]

    custom = repository.get_optional("custom-jd")
    if custom is not None:
        return custom

    skills = repository.list_skills()
    if skills:
        return skills[0]
    raise KeyError("No interview skills are configured.")


def _normalize_search_text(parts: Iterable[str]) -> str:
    return " ".join(part for part in parts if part).lower()


def _keyword_score(haystack: str, keywords: Iterable[str]) -> int:
    score = 0
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if normalized and normalized in haystack:
            score += 1
    return score
