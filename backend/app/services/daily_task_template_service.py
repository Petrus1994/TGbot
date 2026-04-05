from __future__ import annotations


class DailyTaskTemplateService:
    def infer_task_type(self, *, title: str, description: str | None = None) -> str:
        text = f"{title} {description or ''}".lower()

        fitness_keywords = [
            "трен", "пресс", "отжим", "кардио", "зал", "бег", "растяж", "workout",
            "fitness", "push-up", "plank", "abs", "run", "mobility", "exercise",
        ]
        music_keywords = [
            "гитар", "аккорд", "бой", "перебор", "ритм", "пальц", "guitar",
            "chord", "strumming", "fingerstyle", "piano", "vocal", "singing",
        ]
        language_keywords = [
            "англий", "слова", "grammar", "speaking", "listening", "vocabulary",
            "язык", "чтение", "writing", "reading",
        ]
        study_keywords = [
            "изуч", "урок", "конспект", "повтор", "экзам", "курс", "lecture",
            "study", "learn", "practice", "homework",
        ]
        work_keywords = [
            "код", "backend", "frontend", "api", "экран", "таск", "задач", "проект",
            "client", "bug", "feature", "endpoint", "deploy", "refactor", "design",
        ]
        habit_keywords = [
            "вода", "сон", "медитац", "дневник", "привыч", "walk", "sleep",
            "habit", "journal",
        ]
        speech_keywords = [
            "речь", "дикц", "голос", "speech", "pronunciation", "articulation",
            "public speaking",
        ]
        drawing_keywords = [
            "рис", "скетч", "drawing", "sketch", "paint", "illustration",
        ]
        meditation_keywords = [
            "meditation", "breathing", "дыхание", "осознан", "mindfulness",
        ]
        rehab_keywords = [
            "rehab", "recovery", "восстанов", "реабил", "mobility routine",
        ]

        if any(keyword in text for keyword in fitness_keywords):
            return "fitness"
        if any(keyword in text for keyword in music_keywords):
            return "music"
        if any(keyword in text for keyword in language_keywords):
            return "language"
        if any(keyword in text for keyword in study_keywords):
            return "study"
        if any(keyword in text for keyword in work_keywords):
            return "work"
        if any(keyword in text for keyword in habit_keywords):
            return "habit"
        if any(keyword in text for keyword in speech_keywords):
            return "speech"
        if any(keyword in text for keyword in drawing_keywords):
            return "drawing"
        if any(keyword in text for keyword in meditation_keywords):
            return "meditation"
        if any(keyword in text for keyword in rehab_keywords):
            return "rehab"

        return "generic"

    def build_task_guidance(self, task_type: str) -> str:
        mapping = {
            "fitness": (
                "Use detail level 3. Build a mini training protocol. "
                "Include exact sequence, sets/reps or timed intervals, rest if relevant, "
                "technique cues, common mistakes, safe volume for the user's level, "
                "and a clear proof/report format. If relevant, include warm-up and a simpler alternative. "
                "Avoid risky medical claims. Mention to stop if pain appears."
            ),
            "music": (
                "Use detail level 3. Build a mini lesson/practice protocol. "
                "Include warm-up, technical block, application block, concrete timing for each block, "
                "quality criteria, self-check, common mistakes, and proof/report guidance."
            ),
            "language": (
                "Use detail level 2 by default, level 3 if the task is strongly skill-based speaking/pronunciation practice. "
                "Split into very concrete blocks, define material/format, measurable output, self-check, "
                "common mistakes, and proof/report guidance."
            ),
            "study": (
                "Use detail level 2. Define objective, exact blocks, order of execution, "
                "what notes/output to produce, common mistakes, measurable completion rule, "
                "and proof/report guidance."
            ),
            "work": (
                "Use detail level 2. Define the exact deliverable, why it matters today, "
                "a realistic sequence of steps, common execution mistakes, done criteria, "
                "and proof/report guidance."
            ),
            "habit": (
                "Usually use detail level 1 unless the habit has technique or structure. "
                "Keep it simple, measurable, and easy to report."
            ),
            "speech": (
                "Use detail level 3. Include warm-up, articulation/technical block, application block, "
                "quality cues, common mistakes, self-check, and proof/report guidance."
            ),
            "drawing": (
                "Use detail level 3. Include warm-up or setup, focused exercise block, application block, "
                "quality cues, common mistakes, and proof/report guidance."
            ),
            "meditation": (
                "Use detail level 3. Include setup, exact sequence, duration of blocks, attention cues, "
                "common mistakes, self-check, and proof/report guidance."
            ),
            "rehab": (
                "Use detail level 3. Keep volume conservative, include exact order, duration/reps if relevant, "
                "soft technique cues, safe execution notes, and proof/report guidance. "
                "Avoid medical certainty or risky recommendations."
            ),
            "generic": (
                "Choose the smallest sufficient detail level. "
                "Turn the task into a concrete, measurable, realistic action for one day. "
                "No vague abstractions."
            ),
        }
        return mapping.get(task_type, mapping["generic"])