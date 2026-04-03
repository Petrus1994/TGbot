from __future__ import annotations

import copy

from app.services.ai_profiling_service import AIProfilingService


DEFAULT_QUESTION_BANK = [
    {
        "id": "q1",
        "key": "goal_outcome",
        "text": "Что именно ты хочешь получить в итоге?",
        "example_answer": "Хочу выйти на доход 3000$ в месяц за 6 месяцев",
        "priority": 100,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q2",
        "key": "current_level",
        "text": "Где ты сейчас относительно этой цели?",
        "example_answer": "Сейчас я только начинаю и пока не получал результатов",
        "priority": 95,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q3",
        "key": "deadline",
        "text": "За какой срок ты хочешь этого достичь?",
        "example_answer": "Хочу добиться этого за 4 месяца",
        "priority": 90,
        "question_type": "choice_or_text",
        "suggested_options": ["1-3 months", "3-6 months", "6-12 months", "no strict deadline"],
        "allow_free_text": True,
    },
    {
        "id": "q4",
        "key": "resources",
        "text": "Какие у тебя уже есть ресурсы для этой цели?",
        "example_answer": "Есть ноутбук, интернет, базовые знания и доступ к курсу",
        "priority": 80,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q5",
        "key": "constraints",
        "text": "Какие у тебя есть ограничения?",
        "example_answer": "Работаю full-time и могу уделять цели только вечерами",
        "priority": 85,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q6",
        "key": "past_attempts",
        "text": "Ты уже пытался достичь этого раньше?",
        "example_answer": "Да, начинал дважды, но бросал через пару недель",
        "priority": 70,
        "question_type": "text",
        "suggested_options": ["yes", "no"],
        "allow_free_text": True,
    },
    {
        "id": "q7",
        "key": "obstacles",
        "text": "Что обычно тебе мешает двигаться к таким целям?",
        "example_answer": "Прокрастинация, хаос в расписании и быстро теряю фокус",
        "priority": 88,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q8",
        "key": "motivation",
        "text": "Почему эта цель для тебя важна?",
        "example_answer": "Хочу больше свободы, денег и уверенности в себе",
        "priority": 75,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q9",
        "key": "daily_routine",
        "text": "Как обычно выглядит твой день или неделя?",
        "example_answer": "По будням свободен с 19:00 до 22:00, в выходные больше времени",
        "priority": 65,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
    },
    {
        "id": "q10",
        "key": "time_budget",
        "text": "Сколько времени ты реально готов уделять этой цели?",
        "example_answer": "1 час в день по будням и 3 часа в выходные",
        "priority": 92,
        "question_type": "choice_or_text",
        "suggested_options": ["<5 hours/week", "5-10 hours/week", "10+ hours/week"],
        "allow_free_text": True,
    },
    {
        "id": "q11",
        "key": "coach_style",
        "text": "Какой стиль коучинга тебе подходит?",
        "example_answer": None,
        "priority": 60,
        "question_type": "choice",
        "suggested_options": ["aggressive", "balanced", "soft"],
        "allow_free_text": False,
    },
]


class DynamicProfilingService:
    def __init__(self):
        self.ai_service = AIProfilingService()

    async def build_context(self, goal_title: str, goal_description: str | None = None) -> dict:
        questions = self._build_contextual_question_bank(
            goal_title=goal_title,
            goal_description=goal_description,
        )

        return {
            "profiling": {
                "mode": "adaptive",
                "goal_analysis": {
                    "goal_type": self._infer_goal_type(goal_title, goal_description),
                    "difficulty": "medium",
                    "time_horizon": None,
                },
                "questions": questions,
                "answers": {},
                "asked_question_keys": [],
                "skipped_question_keys": [],
                "follow_up_attempts": {},
                "current_question_key": questions[0]["key"],
                "is_completed": False,
                "questions_total_count": len(questions),
                "questions_answered_count": 0,
                "minimum_required_answers": 6,
            }
        }

    async def select_next_step(
        self,
        goal_title: str,
        goal_description: str | None,
        questions: list[dict],
        answers: dict[str, str],
        asked_question_keys: list[str] | None = None,
        skipped_question_keys: list[str] | None = None,
    ) -> dict:
        asked_question_keys = asked_question_keys or []
        skipped_question_keys = skipped_question_keys or []

        remaining_questions = [
            q
            for q in questions
            if q.get("key") not in answers
            and q.get("key") not in asked_question_keys
            and q.get("key") not in skipped_question_keys
        ]

        if not remaining_questions:
            return {
                "is_completed": True,
                "next_question_key": None,
                "reason": "No remaining questions",
                "source": "fallback",
            }

        minimum_required_answers = 6
        force_continue = len(answers) < minimum_required_answers

        try:
            result = await self.ai_service.select_next_question(
                goal_title=goal_title,
                goal_description=goal_description,
                answers=answers,
                candidate_questions=remaining_questions,
            )

            ai_is_completed = bool(result.get("is_completed", False))
            next_question_key = result.get("next_question_key")
            reason = str(result.get("reason") or "")

            if force_continue and ai_is_completed:
                ai_is_completed = False

            if ai_is_completed:
                return {
                    "is_completed": True,
                    "next_question_key": None,
                    "reason": reason or "AI decided profiling is sufficient",
                    "source": "ai",
                }

            if next_question_key:
                matched = next(
                    (q for q in remaining_questions if q.get("key") == next_question_key),
                    None,
                )
                if matched:
                    return {
                        "is_completed": False,
                        "next_question_key": matched["key"],
                        "reason": reason or "AI selected next question",
                        "source": "ai",
                    }

        except Exception:
            pass

        fallback_question = self._select_fallback_question(remaining_questions)

        return {
            "is_completed": False,
            "next_question_key": fallback_question["key"],
            "reason": "Fallback priority-based selection",
            "source": "fallback",
        }

    def _select_fallback_question(self, remaining_questions: list[dict]) -> dict:
        return sorted(
            remaining_questions,
            key=lambda q: int(q.get("priority", 0)),
            reverse=True,
        )[0]

    def _build_contextual_question_bank(
        self,
        goal_title: str,
        goal_description: str | None = None,
    ) -> list[dict]:
        goal_text = f"{goal_title} {goal_description or ''}".lower()
        goal_type = self._infer_goal_type(goal_title, goal_description)

        questions = copy.deepcopy(DEFAULT_QUESTION_BANK)
        for question in questions:
            question["example_answer"] = self._build_contextual_example(
                question_key=question["key"],
                goal_type=goal_type,
                goal_text=goal_text,
                fallback_example=question.get("example_answer"),
            )

        return questions

    def _infer_goal_type(self, goal_title: str, goal_description: str | None = None) -> str:
        text = f"{goal_title} {goal_description or ''}".lower()

        if any(token in text for token in ["доход", "income", "earn", "деньг", "зарплат", "sales", "revenue"]):
            return "income"
        if any(token in text for token in ["плав", "swim", "бассейн"]):
            return "swimming"
        if any(token in text for token in ["барабан", "drum", "музык", "music", "гитара", "piano"]):
            return "music"
        if any(token in text for token in ["похуд", "вес", "fat", "weight", "fitness", "shape"]):
            return "fitness"
        if any(token in text for token in ["бизнес", "business", "startup", "client", "клиент"]):
            return "business"
        if any(token in text for token in ["учеб", "экзам", "study", "learn", "course", "language"]):
            return "study"
        if any(token in text for token in ["привыч", "habit", "discipline", "дисциплин"]):
            return "habit"

        return "generic"

    def _build_contextual_example(
        self,
        question_key: str,
        goal_type: str,
        goal_text: str,
        fallback_example: str | None,
    ) -> str | None:
        examples = {
            "income": {
                "goal_outcome": "Хочу выйти на доход 5000$ в месяц за 6 месяцев.",
                "current_level": "Сейчас у меня доход около 2000$ в месяц и 2 клиента.",
                "deadline": "Хочу прийти к этому за 6 месяцев.",
                "resources": "Есть ноутбук, интернет, опыт в маркетинге и 2 постоянных клиента.",
                "constraints": "Могу уделять цели 2 часа в день и 500$ в месяц на развитие.",
                "past_attempts": "Да, уже пытался расширять клиентскую базу, но делал это несистемно.",
                "obstacles": "Часто распыляюсь и не держу стабильный поток заявок.",
                "motivation": "Хочу больше свободы, сильнее увеличить доход и купить дорогую машину.",
                "daily_routine": "По будням работаю днём, а вечером свободен 2-3 часа.",
                "time_budget": "Реально готов уделять 10 часов в неделю.",
                "coach_style": None,
            },
            "swimming": {
                "goal_outcome": "Хочу уверенно проплывать 2 км без остановки.",
                "current_level": "Сейчас могу проплыть 500 метров без остановки.",
                "deadline": "Хочу прийти к этому за 4 месяца.",
                "resources": "Есть доступ к бассейну, абонемент и базовая техника.",
                "constraints": "Могу ходить в бассейн только 3 раза в неделю после работы.",
                "past_attempts": "Да, раньше тренировался пару месяцев, но потом бросил.",
                "obstacles": "Не держу регулярность и быстро пропускаю тренировки.",
                "motivation": "Хочу улучшить здоровье и чувствовать себя сильнее физически.",
                "daily_routine": "По будням свободен вечером, по выходным утром.",
                "time_budget": "Готов уделять 3 тренировки в неделю по 45-60 минут.",
                "coach_style": None,
            },
            "music": {
                "goal_outcome": "Хочу уверенно играть базовые ритмы на барабанах.",
                "current_level": "Сейчас знаю только самые простые упражнения и ритмы.",
                "deadline": "Хочу заметный прогресс за 3 месяца.",
                "resources": "Есть учебные материалы, пэды и доступ к установке 2 раза в неделю.",
                "constraints": "Не могу шуметь дома поздно вечером.",
                "past_attempts": "Да, начинал заниматься, но быстро терял систему.",
                "obstacles": "Часто прыгаю между упражнениями и не держу регулярность.",
                "motivation": "Хочу развить навык, который реально приносит удовольствие и уверенность.",
                "daily_routine": "По будням у меня есть 30-40 минут вечером, по выходным больше.",
                "time_budget": "Готов уделять 5-6 часов в неделю.",
                "coach_style": None,
            },
            "fitness": {
                "goal_outcome": "Хочу сбросить 8 кг и улучшить форму.",
                "current_level": "Сейчас есть лишний вес и нерегулярные тренировки.",
                "deadline": "Хочу заметный результат за 4-5 месяцев.",
                "resources": "Есть абонемент в зал и возможность готовить дома.",
                "constraints": "Сложно держать питание из-за плотного графика.",
                "past_attempts": "Да, уже пытался худеть, но срывался через пару недель.",
                "obstacles": "Часто ем хаотично и пропускаю тренировки.",
                "motivation": "Хочу чувствовать себя лучше, увереннее и здоровее.",
                "daily_routine": "Рабочие дни плотные, но вечером есть 1 час.",
                "time_budget": "Готов тренироваться 4 раза в неделю и следить за питанием ежедневно.",
                "coach_style": None,
            },
            "business": {
                "goal_outcome": "Хочу запустить бизнес и выйти на первых платящих клиентов.",
                "current_level": "Сейчас идея есть, но системы продаж и продукта ещё нет.",
                "deadline": "Хочу получить первые результаты за 3-6 месяцев.",
                "resources": "Есть опыт, ноутбук, интернет и базовые контакты.",
                "constraints": "Пока ограничен по времени и не могу сильно рисковать деньгами.",
                "past_attempts": "Да, уже пробовал запускаться, но без стабильной системы.",
                "obstacles": "Часто залипаю в идеи и поздно перехожу к продаже.",
                "motivation": "Хочу построить более независимый источник дохода и контроля над своей жизнью.",
                "daily_routine": "Работаю днём, бизнесом могу заниматься вечером и в выходные.",
                "time_budget": "Готов выделять 10-15 часов в неделю.",
                "coach_style": None,
            },
            "study": {
                "goal_outcome": "Хочу выйти на уверенный уровень и закрыть учебную цель.",
                "current_level": "Сейчас база есть, но знаний и практики ещё недостаточно.",
                "deadline": "Хочу прийти к этому за 3 месяца.",
                "resources": "Есть курс, ноутбук и доступ к материалам.",
                "constraints": "После работы сложно держать концентрацию долго.",
                "past_attempts": "Да, уже начинал учиться, но часто бросал без системы.",
                "obstacles": "Откладываю занятия и теряю ритм.",
                "motivation": "Это важно для роста, уверенности и новых возможностей.",
                "daily_routine": "По будням могу заниматься вечером, по выходным — дольше.",
                "time_budget": "Готов уделять 7-8 часов в неделю.",
                "coach_style": None,
            },
            "habit": {
                "goal_outcome": "Хочу выстроить стабильную дисциплину и делать это регулярно.",
                "current_level": "Сейчас у меня нет стабильной системы и всё идёт рывками.",
                "deadline": "Хочу закрепить привычку за 2-3 месяца.",
                "resources": "Есть телефон, трекер привычек и свободные слоты утром.",
                "constraints": "Быстро выпадаю из режима после пары пропусков.",
                "past_attempts": "Да, уже пытался внедрить привычку, но не удерживал ритм.",
                "obstacles": "Срываюсь после первых неудачных дней и теряю последовательность.",
                "motivation": "Хочу стать собраннее и надёжнее в своих действиях.",
                "daily_routine": "Утром и вечером есть короткие окна по 20-30 минут.",
                "time_budget": "Готов уделять этой привычке 20-30 минут в день.",
                "coach_style": None,
            },
            "generic": {},
        }

        domain_examples = examples.get(goal_type, {})
        example = domain_examples.get(question_key)
        if example:
            return example

        return fallback_example