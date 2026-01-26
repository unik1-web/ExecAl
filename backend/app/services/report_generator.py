from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    text: str
    doctor_contact: str | None = None


def generate_recommendations(deviations: list[dict]) -> list[Recommendation]:
    # MVP-уровень: минимальные шаблонные советы.
    if not deviations:
        return [Recommendation(text="Показатели в норме. Продолжайте поддерживать здоровый образ жизни.")]

    recs: list[Recommendation] = []
    for d in deviations:
        test = d.get("test") or d.get("test_name") or "Показатель"
        dev = d.get("deviation")
        if dev == "high":
            recs.append(Recommendation(text=f"{test}: значение выше нормы. Рекомендуется пересдать анализ натощак и обсудить с врачом."))
        elif dev == "low":
            recs.append(Recommendation(text=f"{test}: значение ниже нормы. Рекомендуется уточнить питание/дефициты и обсудить с врачом."))
    return recs or [Recommendation(text="Есть отклонения. Рекомендуется консультация врача.")]

