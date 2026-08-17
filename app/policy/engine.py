from app.policy.models import PolicyDecision
from app.policy.rules import POLICY_RULES


class PolicyEngine:

    AI_MIN_CONFIDENCE = 0.90

    def evaluate(
        self,
        category: str,
        classifier_action: str,
        source: str = "rules",
        confidence: float = 1.0,
    ) -> PolicyDecision:

        rule = POLICY_RULES.get(
            category,
            POLICY_RULES["UNKNOWN"],
        )

        # =========================================
        # AI SAFETY BOUNDARY
        # =========================================

        if source == "ai":

            # A single AI diagnosis cannot establish
            # that a failure is flaky.
            if category == "FLAKY_TEST":

                return PolicyDecision(
                    category=category,
                    risk_level="HIGH",
                    allowed=False,
                    action="ESCALATE",
                    max_attempts=0,
                    requires_approval=True,
                    reason=(
                        "AI cannot establish test flakiness "
                        "from a single pipeline failure. "
                        "Historical evidence is required."
                    ),
                )

            # Do not automatically remediate
            # low-confidence AI diagnoses.
            if confidence < self.AI_MIN_CONFIDENCE:

                return PolicyDecision(
                    category=category,
                    risk_level="HIGH",
                    allowed=False,
                    action="ESCALATE",
                    max_attempts=0,
                    requires_approval=True,
                    reason=(
                        f"AI confidence {confidence:.2f} "
                        f"is below the automatic remediation "
                        f"threshold of "
                        f"{self.AI_MIN_CONFIDENCE:.2f}."
                    ),
                )

        # =========================================
        # CLASSIFIER UNSAFE SIGNAL
        # =========================================

        if (
            classifier_action == "DO_NOT_HEAL"
            and rule.allowed
        ):
            return PolicyDecision(
                category=category,
                risk_level="HIGH",
                allowed=False,
                action="DO_NOT_HEAL",
                max_attempts=0,
                requires_approval=True,
                reason=(
                    "Classifier marked this failure as "
                    "unsafe for automatic healing."
                ),
            )

        return PolicyDecision(
            category=rule.category,
            risk_level=rule.risk_level,
            allowed=rule.allowed,
            action=rule.action,
            max_attempts=rule.max_attempts,
            requires_approval=rule.requires_approval,
            reason=rule.reason,
        )