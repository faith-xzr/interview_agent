import re
from hashlib import md5
from typing import Iterable, List


COMMON_SKILLS = [
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "SQL",
    "MySQL",
    "PostgreSQL",
    "React",
    "Vue",
    "Java",
    "Spring",
    "RAG",
    "LLM",
    "LangChain",
    "向量检索",
    "知识库",
    "Docker",
    "Kubernetes",
    "Linux",
    "Redis",
    "Kafka",
    "Spark",
    "Hadoop",
    "PyTorch",
    "TensorFlow",
    "NLP",
    "Excel",
    "Power BI",
    "数据分析",
]

INDUSTRY_TERMS = ["AI", "人工智能", "金融", "工业", "电商", "医疗", "SaaS", "RAG", "知识库"]


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"[\n。；;.!?！？]+", text)
    return [part.strip(" ，,：:") for part in parts if part.strip(" ，,：:")]


def extract_skills(text: str) -> List[str]:
    found = []
    lower_text = text.lower()
    for skill in COMMON_SKILLS:
        if skill.lower() in lower_text and skill not in found:
            found.append(skill)
    return found


def extract_max_years(text: str) -> int:
    years = [int(value) for value in re.findall(r"(\d{1,2})\s*(?:年|\+)", text)]
    return max(years) if years else 0


def unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def hash_embedding(text: str, dimensions: int = 384) -> List[float]:
    vector = [0.0] * dimensions
    normalized = re.sub(r"\s+", "", text.lower())
    if not normalized:
        return vector
    grams = [normalized[i : i + 2] for i in range(max(1, len(normalized) - 1))]
    for gram in grams:
        digest = md5(gram.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dimensions
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        vector[index] += sign
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))

