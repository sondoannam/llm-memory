"""
Benchmark Scenarios
───────────────────
10 multi-turn conversations covering all rubric-required test groups:
  - profile recall
  - conflict update
  - episodic recall
  - semantic retrieval
  - trim/token budget
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class Turn:
    user: str
    # Optional: what the response MUST contain to pass
    must_contain: List[str] = field(default_factory=list)
    must_not_contain: List[str] = field(default_factory=list)


@dataclass
class Scenario:
    id: int
    name: str
    group: str          # profile | conflict | episodic | semantic | trim
    turns: List[Turn]
    knowledge_seed: List[str] = field(default_factory=list)  # pre-load into semantic mem


SCENARIOS: List[Scenario] = [

    # ── 1. Profile recall: name ────────────────────────────────────────
    Scenario(
        id=1, name="Recall user name after 6 turns", group="profile",
        turns=[
            Turn("Xin chào! Tôi tên là Linh."),
            Turn("Bạn có thể giúp tôi học Python không?"),
            Turn("Tôi muốn bắt đầu với vòng lặp for."),
            Turn("Còn list comprehension thì sao?"),
            Turn("Cảm ơn, tôi đã hiểu rồi."),
            Turn("Bạn có nhớ tên tôi là gì không?",
                 must_contain=["Linh"]),
        ],
    ),

    # ── 2. Conflict update: allergy ────────────────────────────────────
    Scenario(
        id=2, name="Allergy conflict update", group="conflict",
        turns=[
            Turn("Tôi bị dị ứng sữa bò."),
            Turn("Bạn ghi nhận chưa?"),
            Turn("À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò."),
            Turn("Bây giờ profile của tôi ghi gì về dị ứng?",
                 must_contain=["đậu nành"],
                 must_not_contain=["sữa bò"]),
        ],
    ),

    # ── 3. Profile recall: multiple facts ─────────────────────────────
    Scenario(
        id=3, name="Multi-fact profile recall", group="profile",
        turns=[
            Turn("Tên tôi là Minh, 25 tuổi."),
            Turn("Tôi đang làm software engineer."),
            Turn("Mục tiêu của tôi là trở thành ML engineer."),
            Turn("Tôi thích đọc sách về AI."),
            Turn("Hãy tóm tắt những gì bạn biết về tôi.",
                 must_contain=["Minh"]),
        ],
    ),

    # ── 4. Episodic recall: debug lesson ──────────────────────────────
    Scenario(
        id=4, name="Recall previous debug lesson", group="episodic",
        turns=[
            Turn("Tôi đang debug lỗi connection refused khi gọi service B từ service A trong Docker."),
            Turn("Tôi đã thử dùng localhost nhưng không được."),
            Turn("Bạn có gợi ý gì không?"),
            Turn("Ồ dùng docker service name thì được rồi! Cảm ơn bạn, đã xong."),
            Turn("Lần sau tôi bị lỗi tương tự, tôi cần nhớ điều gì?",
                 must_contain=["service"]),
        ],
    ),

    # ── 5. Semantic retrieval: FAQ lookup ─────────────────────────────
    Scenario(
        id=5, name="Retrieve FAQ knowledge chunk", group="semantic",
        knowledge_seed=[
            "To reset your password: go to Settings → Security → Reset Password.",
            "The API rate limit is 100 requests per minute per API key.",
            "Supported file formats: PDF, DOCX, XLSX, PNG, JPG.",
            "To export data: Dashboard → Reports → Export as CSV.",
        ],
        turns=[
            Turn("Xin chào, tôi cần hỏi về sản phẩm."),
            Turn("API của bạn có giới hạn request không?",
                 must_contain=["100"]),
            Turn("Các định dạng file nào được hỗ trợ?",
                 must_contain=["PDF"]),
            Turn("Làm thế nào để export dữ liệu?",
                 must_contain=["Export"]),
        ],
    ),

    # ── 6. Conflict update: preference change ─────────────────────────
    Scenario(
        id=6, name="Preference update conflict", group="conflict",
        turns=[
            Turn("Tôi thích học buổi sáng."),
            Turn("Hãy lên kế hoạch học Python cho tôi vào buổi sáng."),
            Turn("Thật ra tôi thay đổi ý kiến, tôi thích học buổi tối hơn."),
            Turn("Kế hoạch học của tôi nên vào lúc nào?",
                 must_contain=["tối"],
                 must_not_contain=["sáng"]),
        ],
    ),

    # ── 7. Episodic recall: past session topic ────────────────────────
    Scenario(
        id=7, name="Recall past session topic", group="episodic",
        turns=[
            Turn("Hôm nay tôi muốn học về decorators trong Python."),
            Turn("Decorator dùng để làm gì?"),
            Turn("Cho tôi xem ví dụ về @property decorator."),
            Turn("Hiểu rồi, cảm ơn, tôi đã xong phần này."),
            Turn("Tôi đã học gì trong phiên này?",
                 must_contain=["decorator"]),
        ],
    ),

    # ── 8. Token budget / trim ────────────────────────────────────────
    Scenario(
        id=8, name="Context window trim under heavy load", group="trim",
        knowledge_seed=[f"Knowledge chunk {i}: " + "x" * 200 for i in range(20)],
        turns=[
            Turn("Tên tôi là An."),
            Turn("Tôi muốn hỏi nhiều câu hỏi liên tiếp."),
            Turn("Câu hỏi 1: Python list là gì?"),
            Turn("Câu hỏi 2: Dict comprehension dùng như thế nào?"),
            Turn("Câu hỏi 3: Lambda function có dùng được nhiều lần không?"),
            Turn("Câu hỏi 4: Generator vs Iterator khác nhau thế nào?"),
            Turn("Câu hỏi 5: Asyncio dùng khi nào?"),
            Turn("Bạn vẫn nhớ tên tôi chứ?",
                 must_contain=["An"]),
        ],
    ),

    # ── 9. Profile + semantic combined ────────────────────────────────
    Scenario(
        id=9, name="Personalised semantic retrieval", group="semantic",
        knowledge_seed=[
            "Beginner Python resources: automate the boring stuff, python.org tutorial.",
            "Advanced Python resources: Fluent Python, Python Cookbook.",
            "ML resources: fast.ai course, Hands-on ML by Aurélien Géron.",
        ],
        turns=[
            Turn("Tôi là người mới học Python, tên tôi là Hoa."),
            Turn("Trình độ của tôi là beginner."),
            Turn("Bạn có thể gợi ý tài liệu học không?",
                 must_contain=["Python"]),
            Turn("Cảm ơn Hoa đã hỏi câu đó. À ý tôi là cảm ơn bạn!", ),
            Turn("Bạn có nhớ tên tôi và trình độ của tôi không?",
                 must_contain=["Hoa"]),
        ],
    ),

    # ── 10. Full stack: profile + conflict + episodic + semantic ───────
    Scenario(
        id=10, name="Full stack integration test", group="profile",
        knowledge_seed=[
            "Company policy: remote work allowed 3 days/week.",
            "Company policy: annual leave is 15 days/year.",
            "Onboarding checklist: setup VPN, install Docker, join Slack.",
        ],
        turns=[
            Turn("Xin chào! Tôi tên là Khoa, tôi vừa gia nhập công ty."),
            Turn("Chính sách làm remote của công ty là gì?",
                 must_contain=["3"]),
            Turn("Tôi muốn setup môi trường, tôi cần làm gì?",
                 must_contain=["Docker"]),
            Turn("Tôi dị ứng với caffeine."),
            Turn("À thật ra tôi không dị ứng caffeine, tôi nhầm. Tôi dị ứng gluten."),
            Turn("Profile của tôi hiện tại thế nào?",
                 must_contain=["Khoa"],
                 must_not_contain=["caffeine"]),
        ],
    ),
]