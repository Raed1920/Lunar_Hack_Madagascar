from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from app.models import RouteDecision


class LightweightRouter:
    """Deterministic low-latency router (no LLM call)."""

    LEGAL_EMBEDDING_THRESHOLD = 0.72

    LEGAL_KEYWORDS = [
        "law",
        "legal",
        "regulation",
        "compliance",
        "data privacy",
        "gdpr",
        "personal data",
        "sell data",
        "transfer data",
        "foreign",
        "client data",
        "privacy",
        "consent",
        # French
        "juridique",
        "loi",
        "reglement",
        "conformite",
        "donnees personnelles",
        "protection des donnees",
        "confidentialite",
        "consentement",
        "rgpd",
        # Arabic
        "قانون",
        "قانوني",
        "تشريع",
        "امتثال",
        "حماية البيانات",
        "بيانات شخصية",
        "الخصوصية",
        "موافقة",
    ]

    LEGAL_ANCHOR_QUERIES = [
        "is this policy gdpr compliant",
        "can we transfer client data to foreign servers",
        "what consent is required to process personal data",
        "legal requirements for refund and cancellation",
        "compliance risk for data privacy policy",
        "cette politique est-elle conforme au rgpd",
        "pouvons-nous transferer des donnees clients vers des serveurs etrangers",
        "quel consentement est requis pour traiter des donnees personnelles",
        "ما متطلبات الامتثال لسياسة الخصوصية",
        "هل يمكن نقل بيانات العملاء الى خوادم خارجية",
        "ما الموافقة المطلوبة لمعالجة البيانات الشخصية",
    ]

    LEGAL_REGEX_PATTERNS = [
        # English
        r"\b(sell|selling|transfer|share)\b.{0,40}\b(data|personal data|client data)\b",
        r"\b(foreign|cross[-\s]?border|outside the country)\b",

        # French (with typo-friendly stems)
        r"\b(vendre|vente|transferer|transfert|partager)\b.{0,50}\b(donnee|donnees|data)\b",
        r"\b(donnee|donnees)\b.{0,25}\b(personnel\w*|personne\w*)\b",
        r"\b(hors du pays|etranger|transfrontalier|a l'?etranger)\b",
        r"\b(rgpd|conformite|juridique|legal)\b",

        # Arabic
        r"(بيع|نقل|مشاركة).{0,20}(بيانات|بيانات شخصية|بيانات العملاء)",
        r"(خارج البلد|عبر الحدود|خوادم خارجية)",
        r"(الخصوصية|حماية البيانات|امتثال)",
    ]

    RISK_TERMS = {
        # English
        "policy",
        "legal",
        "terms",
        "regulation",
        "compliance",
        "contract",
        "tax",
        "gdpr",
        "privacy",
        "refund",
        "labor law",

        # French
        "politique",
        "juridique",
        "conditions",
        "réglementation",
        "conformité",
        "contrat",
        "impôt",
        "taxe",
        "rgpd",
        "confidentialité",
        "remboursement",
        "droit du travail",

        # Arabic
        "سياسة",
        "قانوني",
        "قانون",
        "شروط",
        "لوائح",
        "تنظيم",
        "امتثال",
        "عقد",
        "ضرائب",
        "ضريبة",
        "حماية البيانات",
        "الخصوصية",
        "استرجاع",
        "استرداد",
        "قانون العمل"
    }

    FAQ_TERMS = {
        "faq",
        "pricing",
        "price",
        "cost",
        "support",
        "sla",
        "refund",
        "cancel",
        "cancellation",
        # French
        "prix",
        "tarif",
        "remboursement",
        "annulation",
        "support",
        # Arabic
        "السعر",
        "الاسعار",
        "استرجاع",
        "الغاء",
        "الدعم",
    }

    FACTUAL_CUES = {
        "source",
        "sources",
        "citation",
        "cite",
        "document",
        "documents",
        "according to",
        "evidence",
        "reference",
        "policy says",
        "official",
        "benchmark",
        "standard",
        "requirement",
        "requirements",
        # French
        "source officielle",
        "preuves",
        "selon",
        "reference",
        # Arabic
        "المصدر",
        "المصادر",
        "مرجع",
        "دليل",
    }

    STRATEGY_CUES = {
        "plan",
        "strategy",
        "roadmap",
        "recommend",
        "recommendation",
        "improve",
        "optimize",
        "growth",
        "ideas",
        "brainstorm",
        "execute",
        # French
        "planifier",
        "strategie",
        "recommandation",
        "ameliorer",
        # Arabic
        "خطة",
        "استراتيجية",
        "توصية",
        "تحسين",
    }

    def route(self, message: str) -> RouteDecision:
        lowered = self._normalize_text(message)
        tokens = self._tokenize(lowered)

        legal_embedding_score = self._legal_embedding_score(lowered)
        legal_rag_trigger = self.should_use_rag(lowered, legal_embedding_score)

        risk_hits = self._count_hits(lowered, tokens, self.RISK_TERMS)
        faq_hits = self._count_hits(lowered, tokens, self.FAQ_TERMS)
        factual_hits = self._count_hits(lowered, tokens, self.FACTUAL_CUES)
        strategy_hits = self._count_hits(lowered, tokens, self.STRATEGY_CUES)

        starts_with_factual_question = bool(re.match(r"^(what|when|where|who|which)\b", lowered))
        has_question_mark = "?" in lowered

        if legal_rag_trigger or risk_hits > 0:
            intent = "risk_check"
            risk_level = "high"
        elif faq_hits > 0:
            intent = "faq"
            risk_level = "low"
        else:
            intent = "analysis"
            risk_level = "medium"

        rag_score = 0
        reasons: list[str] = []

        if legal_rag_trigger:
            rag_score += 5
            reasons.append(f"legal trigger (embedding_score={legal_embedding_score:.2f})")
        if risk_hits:
            rag_score += 4
            reasons.append("risk/compliance query")
        if faq_hits:
            rag_score += 2
            reasons.append("faq/product info query")
        if factual_hits:
            rag_score += 3
            reasons.append("explicit source/evidence cue")
        if starts_with_factual_question:
            rag_score += 1
            reasons.append("factual WH-question")
        if has_question_mark and len(tokens) <= 18:
            rag_score += 1
            reasons.append("short question")
        if strategy_hits:
            rag_score -= 2
            reasons.append("strategy/generation phrasing")

        requires_rag = legal_rag_trigger or rag_score >= 3 or intent in {"risk_check", "faq"}

        # Calibrated deterministic confidence from routing signal strength.
        confidence = 0.6
        confidence += min((risk_hits * 0.08) + (faq_hits * 0.05) + (factual_hits * 0.06), 0.22)
        confidence = max(0.55, min(confidence, 0.92))

        rationale = ", ".join(dict.fromkeys(reasons)) if reasons else "default route"
        return RouteDecision(
            intent=intent,
            requires_rag=requires_rag,
            risk_level=risk_level,
            confidence=confidence,
            rationale=f"{rationale}; rag_score={rag_score}",
        )

    def should_use_rag(self, user_message: str, embedding_score: float) -> bool:
        return (
            self._keyword_match(user_message)
            or self._regex_legal_match(user_message)
            or self._fuzzy_keyword_match(user_message)
            or embedding_score > self.LEGAL_EMBEDDING_THRESHOLD
        )

    def _keyword_match(self, user_message: str) -> bool:
        msg = self._normalize_text(user_message)
        return any(keyword in msg for keyword in self.LEGAL_KEYWORDS)

    def _regex_legal_match(self, user_message: str) -> bool:
        msg = self._normalize_text(user_message)
        return any(re.search(pattern, msg, flags=re.IGNORECASE) for pattern in self.LEGAL_REGEX_PATTERNS)

    def _fuzzy_keyword_match(self, user_message: str) -> bool:
        msg = self._normalize_text(user_message)
        msg_tokens = self._tokenize(msg)
        legal_tokens: set[str] = set()
        for keyword in self.LEGAL_KEYWORDS:
            legal_tokens.update(self._tokenize(self._normalize_text(keyword)))

        for token in msg_tokens:
            if len(token) < 5:
                continue
            for legal_token in legal_tokens:
                if len(legal_token) < 5:
                    continue
                similarity = SequenceMatcher(None, token, legal_token).ratio()
                if similarity >= 0.88:
                    return True
        return False

    def _legal_embedding_score(self, user_message: str) -> float:
        """Lightweight semantic proxy without external model calls.

        We combine token overlap and sequence similarity against legal anchors.
        """
        normalized_message = self._normalize_text(user_message)
        if not normalized_message:
            return 0.0

        msg_tokens = self._tokenize(normalized_message)
        best = 0.0
        for anchor in self.LEGAL_ANCHOR_QUERIES:
            normalized_anchor = self._normalize_text(anchor)
            anchor_tokens = self._tokenize(normalized_anchor)
            union = len(msg_tokens | anchor_tokens)
            jaccard = (len(msg_tokens & anchor_tokens) / union) if union else 0.0
            sequence_ratio = SequenceMatcher(None, normalized_message, normalized_anchor).ratio()
            score = max(jaccard, sequence_ratio)
            if score > best:
                best = score

        return best

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"\w+", text, flags=re.UNICODE))

    @staticmethod
    def _normalize_text(text: str) -> str:
        value = unicodedata.normalize("NFKC", (text or "").strip().lower())
        # Remove Latin diacritics for robust French matching while preserving Arabic script.
        decomposed = unicodedata.normalize("NFKD", value)
        stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
        return unicodedata.normalize("NFKC", stripped)

    @staticmethod
    def _count_hits(text: str, tokens: set[str], phrases: set[str]) -> int:
        hits = 0
        for phrase in phrases:
            if " " in phrase:
                if phrase in text:
                    hits += 1
            elif phrase in tokens:
                hits += 1
        return hits
